
import os, json
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
app = Flask(__name__)

SYSTEM = """Tu es Commercia AI, un community manager expert pour commerces de proximité.
Tu crées des contenus concrets, commerciaux, élégants, non génériques et immédiatement publiables.
Tu écris toujours en français. Tu évites les promesses excessives. Tu adaptes le ton à la marque.
Réponds UNIQUEMENT en JSON valide avec les clés:
summary, posts, reels, stories, calendar, review_reply, commercial_offer.
posts = tableau de 3 objets {title, caption, hashtags, cta}
reels = tableau de 2 objets {title, hook, shots, overlay_text, caption}
stories = tableau de 4 objets {title, content, interaction}
calendar = tableau de 7 objets {day, content_type, topic, goal}
review_reply = chaîne
commercial_offer = objet {headline, body, cta}
"""

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/health")
def health():
    return {"ok": True, "ai_configured": bool(os.getenv("OPENAI_API_KEY"))}

@app.post("/api/generate")
def generate():
    if not os.getenv("OPENAI_API_KEY"):
        return jsonify({
            "error": "OPENAI_API_KEY manquante. Ajoute-la dans le fichier .env puis redémarre l'application."
        }), 400

    data = request.get_json(force=True)
    business = data.get("business", "Sur un Plateau")
    activity = data.get("activity", "Plateaux de fruits raffinés et événementiel")
    location = data.get("location", "Paris & Île-de-France")
    positioning = data.get("positioning", "Premium, artisanal, frais, élégant")
    audience = data.get("audience", "Particuliers et entreprises")
    offer = data.get("offer", "Créations de fruits frais sur commande")
    objective = data.get("objective", "Obtenir plus de demandes de devis et de commandes par Instagram")
    notes = data.get("notes", "")

    prompt = f"""
MARQUE: {business}
ACTIVITÉ: {activity}
ZONE: {location}
POSITIONNEMENT: {positioning}
CIBLE: {audience}
OFFRE À POUSSER: {offer}
OBJECTIF: {objective}
NOTES: {notes}

Conçois une campagne Instagram complète de 7 jours.
Pour cette marque, privilégie la valeur visuelle, le savoir-faire artisanal, les coulisses,
les créations sur mesure et les appels à la commande par message privé.
Les hashtags doivent être crédibles et peu spammy.
"""

    client = OpenAI()
    try:
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5.6"),
            input=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt}
            ],
            text={"format": {"type": "json_object"}}
        )
        raw = response.output_text
        result = json.loads(raw)
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)

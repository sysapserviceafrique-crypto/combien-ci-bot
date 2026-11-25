import os, csv, io, re, time, hashlib, unicodedata, urllib.request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# ---- À MODIFIER SI BESOIN ----
SHEET_ID = "1uMrkenSj1VWQ5lgzYWLbjPy7cAzWbMuSo7Egcv8YN3E"
CONTACT = "Écrivez-nous : [VOTRE CONTACT ICI]"
# --------------------------------
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
TOKEN = os.environ.get("BOT_TOKEN")  # le token n'est jamais écrit dans le code

NOTE = ("\nPrix plafonnés officiels, valables à Abidjan et dans un rayon de 30 km. "
        "Ailleurs, un supplément de transport s'applique.\n"
        "Prix non respecté ? Appelez le 1343 (gratuit).")

_cache = {"t": 0, "rows": []}

def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")

def load_rows():
    if time.time() - _cache["t"] > 300:  # recharge le tableau toutes les 5 minutes
        with urllib.request.urlopen(CSV_URL, timeout=15) as r:
            text = r.read().decode("utf-8")
        rows = list(csv.DictReader(io.StringIO(text)))
        _cache["rows"] = [r for r in rows if (r.get("produit") or "").strip()]
        _cache["t"] = time.time()
    return _cache["rows"]

def fmt_price(v):
    d = re.sub(r"\D", "", v or "")
    return f"{int(d):,}".replace(",", " ") + " FCFA" if d else "prix à venir"

def fmt_row(r):
    return f"• {r['produit']} ({r['unite']}) : {fmt_price(r['prix_fcfa'])}"

def search(q):
    words = norm(q).split()
    return [r for r in load_rows()
            if all(w in norm(r["produit"] + " " + r["categorie"]) for w in words)]

async def send(update, lines, footer=NOTE):
    text = "\n".join(lines) + "\n" + footer
    for i in range(0, len(text), 4000):
        await update.message.reply_text(text[i:i + 4000])

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Bienvenue sur COMBIEN CI 🇨🇮\nLes prix fixes officiels, pour lutter contre la vie chère.\n\n"
        "Écrivez le nom d'un produit (ex : riz, huile, sucre) ou tapez /aide.")

async def aide(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/prix riz - prix fixe d'un produit\n/categories - voir les catégories\n"
        "/recherche sucre - chercher un produit\n/signaler - signaler un prix non respecté\n"
        "/contact - nous contacter\n\nVous pouvez aussi écrire directement le nom d'un produit.")

async def prix(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = " ".join(ctx.args)
    if not q:
        await update.message.reply_text("Précisez un produit, par exemple : /prix riz")
        return
    res = search(q)
    if not res:
        await update.message.reply_text("Aucun produit trouvé. Essayez un autre mot (riz, huile, sucre, pain...).")
        return
    await send(update, [fmt_row(r) for r in res])

async def categories(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = " ".join(ctx.args)
    if q:
        res = [r for r in load_rows() if norm(q) in norm(r["categorie"])]
        if res:
            await send(update, [fmt_row(r) for r in res])
            return
    cats = sorted({r["categorie"] for r in load_rows()})
    await update.message.reply_text("Catégories :\n" + "\n".join("• " + c for c in cats) +
                                    "\n\nTapez par exemple : /categories alimentation")

async def signaler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Un commerçant dépasse le prix plafonné ? Appelez le numéro vert gratuit 1343 du ministère du Commerce.")

async def contact(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(CONTACT)

async def texte(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    res = search(update.message.text)
    if res:
        await send(update, [fmt_row(r) for r in res])
    else:
        await update.message.reply_text("Aucun produit trouvé. Essayez : riz, huile, sucre, pain, lait, tomate, pâtes.")

def main():
    if not TOKEN:
        raise SystemExit("BOT_TOKEN manquant")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("aide", aide))
    app.add_handler(CommandHandler(["prix", "recherche"], prix))
    app.add_handler(CommandHandler("categories", categories))
    app.add_handler(CommandHandler("signaler", signaler))
    app.add_handler(CommandHandler("contact", contact))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, texte))
    base = os.environ.get("RENDER_EXTERNAL_URL")  # fourni automatiquement par Render
    if base:
        path = hashlib.sha256(TOKEN.encode()).hexdigest()[:32]
        app.run_webhook(listen="0.0.0.0", port=int(os.environ.get("PORT", "10000")),
                        url_path=path, webhook_url=f"{base}/{path}")
    else:
        app.run_polling()

if __name__ == "__main__":
    main()

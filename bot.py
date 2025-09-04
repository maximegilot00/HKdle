import discord
import requests
import random
import os

# ========================
# 🔑 CONFIG
# ========================
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
API_KEY = os.getenv("API_KEY")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

RANGE = "Hollowdle!B2:K48"  # adapte à la taille de ton tableau

# ========================
# 📊 CHARGEMENT DES DONNÉES
# ========================
def load_bosses():
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{RANGE}?key={API_KEY}"
    response = requests.get(url)
    data = response.json()
    headers = data["values"][0]        # première ligne = titres
    rows = data["values"][1:]          # lignes suivantes = données
    return [dict(zip(headers, row)) for row in rows]

bosses = load_bosses()

# ========================
# 🔍 LOGIQUE DU JEU
# ========================
def pick_boss():
    return random.choice(bosses)

def compare_guess(guess, target):
    result = []
    fields = ["Type", "First Encounter", "Reward", "Attacks", "Ascend HP", "HasPhases", "CanStagger"]

    for field in fields:
        g_val = guess.get(field, "")
        t_val = target.get(field, "")

        # Booléens convertis en Yes/No
        if field in ["HasPhases", "CanStagger"]:
            g_val_display = "Yes" if g_val.lower() in ["true", "yes"] else "No"
            t_val_display = "Yes" if t_val.lower() in ["true", "yes"] else "No"
        else:
            g_val_display = g_val
            t_val_display = t_val

        # Valeur exacte
        if g_val_display == t_val_display:
            result.append(f"✅ {field}: {g_val_display}")

        # Comparaison numérique pour Ascend HP
        elif field == "Ascend HP":
            try:
                g_hp, t_hp = int(g_val), int(t_val)
                arrow = "🔼" if g_hp < t_hp else "🔽"
                result.append(f"❌ {field}: {g_val} {arrow}")
            except:
                result.append(f"❌ {field}: {g_val}")

        # Champs sous forme de liste (Attacks, Reward)
        elif field in ["Attacks", "Reward"]:
            g_list = [x.strip() for x in g_val.split(",")]
            t_list = [x.strip() for x in t_val.split(",")]
            common = set(g_list).intersection(t_list)
            if common:
                result.append(f"🔶 {field}: {g_val_display} (partiel)")
            else:
                result.append(f"❌ {field}: {g_val_display}")

        # Champs texte simples
        else:
            result.append(f"❌ {field}: {g_val_display}")

    return "\n".join(result)

# ========================
# 🤖 DISCORD BOT
# ========================
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Parties individuelles par joueur
current_bosses = {}  # clé = user_id, valeur = {"boss": ..., "guesses": ...}
player_stats = {}    # clé = user_id, valeur = {"games": ..., "total_guesses": ...}

@client.event
async def on_ready():
    print(f"✅ Bot {client.user} connecté !")

@client.event
async def on_message(message):
    if message.author == client.user:
        return
        
    #if message.channel.name != "bot":
    #    return

    user_id = message.author.id

    # =====================
    # Start a new game
    # =====================
    if message.content.startswith("!start"):
        current_bosses[user_id] = {"boss": pick_boss(), "guesses": 0}
        await message.channel.send("🎮 A boss has been chosen for you! Guess with !guess <name>.")

    # =====================
    # List all bosses
    # =====================
    elif message.content.startswith("!list"):
        boss_names = [b["Name"] for b in bosses]
        embed = discord.Embed(
            title="📜 List of Bosses",
            color=discord.Color.blue()
        )

        chunk_size = 8
        for i in range(0, len(boss_names), chunk_size):
            chunk = boss_names[i:i+chunk_size]
            embed.add_field(
                name="\u200b",
                value="\n".join(chunk),
                inline=True
            )

        await message.channel.send(embed=embed)

    # =====================
    # Forfeit current game
    # =====================
    elif message.content.startswith("!ff"):
        if user_id in current_bosses:
            boss_name = current_bosses[user_id]["boss"]["Name"]
            guesses = current_bosses[user_id]["guesses"]

            # Update stats
            guesses = current_bosses[user_id]["guesses"]
            if user_id not in player_stats:
                player_stats[user_id] = {"won": 0, "forfeit": 1, "total_guesses_won": 0}
            else:
                player_stats[user_id]["forfeit"] += 1

            del current_bosses[user_id]
            await message.channel.send(f"💀 You forfeited the current game. The boss was **{boss_name}**.")
        else:
            await message.channel.send("You don't have an active game. Start one with `!start`.")

    # =====================
    # Make a guess
    # =====================
    elif message.content.startswith("!guess"):
        if user_id not in current_bosses:
            await message.channel.send("No game in progress. Start a new game with !start.")
            return

        guess_name = message.content.replace("!guess ", "").strip()
        guess = next((b for b in bosses if b["Name"].lower() == guess_name.lower()), None)

        if not guess:
            await message.channel.send("❌ Unknown boss 😅")
            return
            
        current = current_bosses[user_id]
        current["guesses"] += 1
        current_boss = current["boss"]

        if guess["Name"].lower() == current_boss["Name"].lower():
            embed = discord.Embed(
                title=f"🎉 Congrats! It was **{current_boss['Name']}**",
                color=discord.Color.green()
            )
            if "Image" in current_boss:
                embed.set_image(url=current_boss["Image"])
            await message.channel.send(embed=embed)

            # Update stats
            guesses = current["guesses"]
            if user_id not in player_stats:
                player_stats[user_id] = {"won": 1, "forfeit": 0, "total_guesses_won": guesses}
            else:
                player_stats[user_id]["won"] += 1
                player_stats[user_id]["total_guesses_won"] += guesses

            del current_bosses[user_id]
        else:
            result = compare_guess(guess, current_boss)
            embed = discord.Embed(
                title=f"Results for **{guess['Name']}**",
                description=result,
                color=discord.Color.orange()
            )
            if "Image" in current_boss:
                embed.set_image(url=guess["Image"])

            await message.channel.send(embed=embed)

    # =====================
    # Player stats
    # =====================
    elif message.content.startswith("!stats"):
        if user_id in player_stats:
            stats = player_stats[user_id]
            average_guesses = (
                stats["total_guesses_won"] / stats["won"] if stats["won"] > 0 else 0
            )

            await message.channel.send(
                f"📊 Stats for {message.author.name}:\n"
                f"Games won: {stats['won']}\n"
                f"Games forfeited: {stats['forfeit']}\n"
                f"Average guesses per win: {average_guesses:.2f}"
            )
        else:
            await message.channel.send("You have not played any games yet.")
            
# ========================
# Run bot
# ========================
try:
    client.run(DISCORD_TOKEN)
except Exception as e:
    print("Erreur :", e)
input("Appuyez sur Entrée pour fermer…")
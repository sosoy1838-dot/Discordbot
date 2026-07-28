MESSAGE_TEMPLATES = {
    "alap": {
        "kind": "embed",
        "title": "📢 Fontos bejelentés",
        "message": (
            "Sziasztok!\n\n"
            "Ide írhatod az előre elkészített üzenetet.\n\n"
            "Szerver neve: **{server}**"
        ),
        "footer": "Automatikus közlemény",
        "color": 0x5865F2,
    },

    "karbantartas": {
        "kind": "embed",
        "title": "🔧 Karbantartás",
        "message": (
            "A szerveren hamarosan karbantartás kezdődik.\n\n"
            "Köszönjük a türelmet!"
        ),
        "footer": "Szerverinformáció",
        "color": 0xF1C40F,
    },

    "sima-uzenet": {
        "kind": "text",
        "message": (
            "Ez egy Python-fájlban megírt sima üzenet."
        ),
    },
}
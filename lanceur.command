#!/bin/zsh

# Lance TPStudio depuis son propre dossier, quel que soit l'endroit depuis
# lequel ce fichier est ouvert dans le Finder.
PROJECT_DIR="${0:A:h}"
APP_FILE="$PROJECT_DIR/src/tpstudio/web/app.py"

cd "$PROJECT_DIR" || {
    echo "Impossible d'accéder au dossier de TPStudio."
    read -k 1 "?Appuyez sur une touche pour fermer cette fenêtre."
    exit 1
}

if [[ -x "$PROJECT_DIR/.venv/bin/python3" ]]; then
    PYTHON_BIN="$PROJECT_DIR/.venv/bin/python3"
elif [[ -x "/opt/anaconda3/bin/python3" ]]; then
    PYTHON_BIN="/opt/anaconda3/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "Python 3 est introuvable. Installez ou réparez Anaconda, puis réessayez."
    read -k 1 "?Appuyez sur une touche pour fermer cette fenêtre."
    exit 1
fi

if [[ ! -f "$APP_FILE" ]]; then
    echo "Le programme TPStudio est introuvable dans :"
    echo "$APP_FILE"
    read -k 1 "?Appuyez sur une touche pour fermer cette fenêtre."
    exit 1
fi

export PYTHONPATH="$PROJECT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

if ! "$PYTHON_BIN" -c "import streamlit" >/dev/null 2>&1; then
    echo "Streamlit n'est pas disponible dans l'environnement Python sélectionné :"
    echo "$PYTHON_BIN"
    echo
    echo "Lancez TPStudio depuis l'environnement Anaconda qui contient ses dépendances."
    read -k 1 "?Appuyez sur une touche pour fermer cette fenêtre."
    exit 1
fi

# Le Finder ne transmet pas nécessairement les variables définies dans un
# terminal. Charge donc la clé locale de TPStudio, sans l'afficher et sans
# remplacer une clé qui serait déjà présente dans l'environnement.
if [[ -z "${OPENAI_API_KEY:-}" && -f "$PROJECT_DIR/.env.local" ]]; then
    OPENAI_KEY_FROM_FILE="$(
        "$PYTHON_BIN" -c \
            'import sys; from dotenv import dotenv_values; print(dotenv_values(sys.argv[1]).get("OPENAI_API_KEY", ""), end="")' \
            "$PROJECT_DIR/.env.local"
    )"
    if [[ -n "$OPENAI_KEY_FROM_FILE" ]]; then
        export OPENAI_API_KEY="$OPENAI_KEY_FROM_FILE"
    fi
    unset OPENAI_KEY_FROM_FILE
fi

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "Attention : la clé API OpenAI n'a pas été trouvée."
    echo "L'analyse sémantique ne sera pas disponible."
    echo
fi

echo "Démarrage de TPStudio…"
echo "Cette fenêtre doit rester ouverte pendant l'utilisation."
echo

"$PYTHON_BIN" -m streamlit run "$APP_FILE" \
    --server.address localhost \
    --server.headless false \
    --browser.gatherUsageStats false

EXIT_STATUS=$?
if [[ $EXIT_STATUS -ne 0 ]]; then
    echo
    echo "TPStudio s'est arrêté avec une erreur."
    read -k 1 "?Appuyez sur une touche pour fermer cette fenêtre."
fi

exit $EXIT_STATUS

     1	# Dockerfile pour nuvio-configuration
     2	# Permet d'exécuter la génération de backdrops dans un environnement reproductible
     3	
     4	FROM python:3.12-slim
     5	
     6	WORKDIR /app
     7	
     8	# Installation des dépendances système nécessaires pour Pillow
     9	RUN apt-get update && apt-get install -y --no-install-recommends \
    10	    libjpeg-dev \
    11	    zlib1g-dev \
    12	    libpng-dev \
    13	    && rm -rf /var/lib/apt/lists/*
    14	
    15	# Copie et installation des dépendances Python
    16	COPY requirements.txt .
    17	RUN pip install --no-cache-dir -r requirements.txt
    18	
    19	# Copie du code source
    20	COPY . .
    21	
    22	# Variable d'environnement pour le buffer de stdout (logging en temps réel)
    23	ENV PYTHONUNBUFFERED=1
    24	
    25	# Commande par défaut : générer les backdrops avec mode mosaïque
    26	# Vous pouvez surcharger cette commande lors de l'exécution
    27	CMD ["python3", "scripts/generer_backdrops.py", "--mosaique"]
    28	

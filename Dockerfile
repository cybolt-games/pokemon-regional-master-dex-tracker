# Regional Dex Buddy — static site plus a small collection API.
# No dependencies beyond the Python standard library.
FROM python:3.12-slim

WORKDIR /app

# The app itself: static site, server, and the config it reads at build time.
# Run `python3 setup.py` on the host first — sprites and cover art are fetched
# rather than shipped, and this copies them in.
COPY serve.py config.json games.json ./
COPY site/ ./site/

RUN test -d /app/site/assets/sprites || (echo \
  "site/assets/sprites is missing. Run 'python3 setup.py' before building." \
  && exit 1)

# Collection state is a CSV at the repo root. Mount it to keep progress across
# rebuilds:  -v "$(pwd)/collection.csv:/app/collection.csv"
RUN printf 'game,dex,dex_number,species,caught\n' > /app/collection.csv

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/config.json', timeout=2).status==200 else 1)"

CMD ["python3", "serve.py", "8000"]

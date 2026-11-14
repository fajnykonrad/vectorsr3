# Granja de señales: une tu PC esta noche (10 minutos de setup)

Varias máquinas preguntan el mismo problema en variantes distintas y luego
votamos. Cuantos más PCs, antes acaba y más robusto el ensemble. Todo
determinista (temperatura 0), cumple las reglas del datathon.

## Lo que necesitas en tu PC (Windows/Mac/Linux)

1. Python 3.10+
2. Git
3. ~900 MB libres para el modelo

## Setup (una sola vez)

```
git clone https://github.com/fajnykonrad/vectorsr3.git
cd vectorsr3

# descarga el modelo (835 MB, verificado con su SHA256)
curl -L -o Qwen_Qwen3.5-0.8B-Q8_0.gguf "https://huggingface.co/bartowski/Qwen_Qwen3.5-0.8B-GGUF/resolve/f36b1ea49a332ede8fe5f389bbf5b3575ef71f48/Qwen_Qwen3.5-0.8B-Q8_0.gguf"

# llama.cpp: descarga el binario para tu sistema
#   Windows: https://github.com/ggml-org/llama.cpp/releases/download/b12359/llama-b12359-bin-win-cpu-x64.zip
#   Mac: brew install llama.cpp
#   Linux: compila o pide ayuda al equipo
```

## Arrancar tu servidor (déjalo abierto)

```
llama-server -m Qwen_Qwen3.5-0.8B-Q8_0.gguf --host 127.0.0.1 --port 8081 --threads 8 --ctx-size 4096 --parallel 1 --cache-ram 0 --jinja --reasoning off --reasoning-budget 0
```

(En Windows usa `^` en vez de `\` para el salto de línea, o ponlo todo en
una línea.)

## Recolectar TU vista (el coordinador te dice cuál)

```
python collect_views.py --view base          # PC 1
python collect_views.py --view value-first   # PC 2
python collect_views.py --view eliminate     # PC 3
python collect_views.py --view careful       # PC 4 (o el 1 cuando acabe)
python collect_views.py --view reversed      # PC 5 (o el 2 cuando acabe)
```

Si sois más PCs que vistas, se puede trocear una vista entre varias
máquinas: `--offset 0 --stride 2` y `--offset 1 --stride 2`.

## Cuando acabes

```
git checkout -b farm-<tu-vista>
git add data/signals-val-view-<tu-vista>.jsonl
git commit -m "farm: <vista>"
git push origin farm-<tu-vista>
```

Y avisa al coordinador. Nada de lo que subas contiene datos de M3Kang:
las señales (números + letras) no son contenido del dataset.

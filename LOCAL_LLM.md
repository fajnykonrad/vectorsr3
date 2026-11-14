# Collect local en el laptop (plan B mientras la placa se configura)

Mismo modelo, mismas señales: el GGUF descargado es exactamente el que la
placa usa (revisión y SHA256 fijados en config.env). Lo único distinto es el
CPU (AVX2 en vez de NEON), lo que cambia las últimas cifras decimales de los
logprobs — irrelevante para el fit.

## 1. Arrancar los dos servidores (dos terminales)

```
# Terminal 1: lenguaje model, puerto 8081
C:\UPC\Datathon\llama-win\llama-server.exe ^
  -m C:\UPC\Datathon\models\Qwen_Qwen3.5-0.8B-Q8_0.gguf ^
  --host 127.0.0.1 --port 8081 --threads 8 --ctx-size 4096 ^
  --parallel 1 --cache-ram 0 --ctx-checkpoints 2 ^
  --jinja --reasoning off --reasoning-budget 0 --alias qwen3.5-0.8b

# Terminal 2: embeddings, puerto 8082
C:\UPC\Datathon\llama-win\llama-server.exe ^
  -m C:\UPC\Datathon\models\bge-small-en-v1.5-q8_0.gguf ^
  --embedding --host 127.0.0.1 --port 8082 --threads 8 ^
  --ctx-size 512 --batch-size 512 --ubatch-size 512 --parallel 1 --cache-ram 0
```

Check en un tercer terminal:

```
curl http://127.0.0.1:8081/health
curl http://127.0.0.1:8082/health
```

## 2. Verificar los GGUF (SHA256 de config.env)

```
Get-FileHash models\Qwen_Qwen3.5-0.8B-Q8_0.gguf -Algorithm SHA256
# esperado 7182e2362766bb9569209bbc24cf1a4cdfbb8ab161babdb2080c84fa62c08c2f
Get-FileHash models\bge-small-en-v1.5-q8_0.gguf -Algorithm SHA256
# esperado ec38e8da142596baa913124ae50550de284b6916bf59577ef2f0cb9660c2f514
```

## 3. Collect + fit (en el clon vectorsr3)

```
cd C:\UPC\Datathon\vectorsr3
..\datathon-UPC-maths-qualcomm-arduino-unoq-main\.venv\Scripts\python.exe collect.py --languages eng --limit 300
..\datathon-UPC-maths-qualcomm-arduino-unoq-main\.venv\Scripts\python.exe fit_model.py
```

- `collect.py` necesita `data/index.db` (votos kNN): constrúyelo antes con
  `laptop/build_index_local.py`. Si no está, usa `--no-index` (fit peor).
- Reanudable: las claves ya en `data/signals.jsonl` se saltan.
- En el laptop el collect va MUCHO más rápido que en la placa (~1-2 s por
  problema en vez de 9): 300 problemas son 5-10 minutos.

## 4. Evaluar y empujar

```
python eval.py --limit 50 --no-fusion --name raw-laptop
python eval.py --limit 50 --name fused-laptop-v1
```

Los números del laptop no son los de la placa (prefill más rápido), pero
comparan raw contra fused con el mismo modelo. `data/model.json` es el
artefacto: se copia a la placa con adb push cuando esté lista.

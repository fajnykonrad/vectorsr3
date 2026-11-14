# Checklist de la placa (Arduino UNO Q)

Pasos 0-8 del README, condensados. El objetivo: que la placa esté lista para
`collect.py` y `eval.py` lo antes posible. Cada paso tiene su check; no pases
al siguiente sin pasarlo.

## Paso 0-1: Conexión y chequeo (~20 min)

```
ssh arduino@<IP>          # la IP sale en App Lab
free -h                   # ~3.6 Gi total
df -h ~                   # >= 2 GiB en Avail
timedatectl | grep synchronized   # debe decir yes
curl -sI https://huggingface.co | head -1   # HTTP/2 200
```

Si el Wi-Fi no va: `adb shell` por USB (App Lab lo usa).

## Paso 2: Build tools (~5 min)

```
sudo apt-get update
sudo apt-get install -y build-essential cmake git pkg-config libssl-dev curl wget ca-certificates python3 sqlite3 jq tmux
gcc --version | head -1 && cmake --version | head -1 && python3 --version
```

## Paso 3: llama.cpp (~30 min, DENTRO DE TMUX)

```
tmux                                # si se cae el SSH, la build sigue
mkdir -p ~/llama.cpp && cd ~/llama.cpp
git init
git remote add origin https://github.com/ggml-org/llama.cpp.git
git fetch --depth 1 origin 2cbe0ec429b849a88664e0f62388fc92a5abd699
git checkout FETCH_HEAD
cmake -B build -DGGML_NATIVE=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j4 --target llama-server llama-cli
```

Check: `~/llama.cpp/build/bin/llama-server --version` -> `build 1, commit 2cbe0ec`

## Paso 4: Modelos (~5 min)

```
mkdir -p ~/models && cd ~/models
wget --continue https://huggingface.co/bartowski/Qwen_Qwen3.5-0.8B-GGUF/resolve/f36b1ea49a332ede8fe5f389bbf5b3575ef71f48/Qwen_Qwen3.5-0.8B-Q8_0.gguf
wget --continue https://huggingface.co/CompendiumLabs/bge-small-en-v1.5-gguf/resolve/d32f8c040ea3b516330eeb75b72bcc2d3a780ab7/bge-small-en-v1.5-q8_0.gguf
sha256sum --check <<'EOF'
7182e2362766bb9569209bbc24cf1a4cdfbb8ab161babdb2080c84fa62c08c2f  Qwen_Qwen3.5-0.8B-Q8_0.gguf
ec38e8da142596baa913124ae50550de284b6916bf59577ef2f0cb9660c2f514  bge-small-en-v1.5-q8_0.gguf
EOF
```

## Pasos 5-7: Hello worlds + servicios

Hello world del LLM (paso 5.4 del README: curl a 8081) y de embeddings
(paso 6.2: curl a 8082, 384 números). Luego los servicios systemd, tal cual
los comandos `sudo tee /etc/systemd/system/math-llm.service ...` y
`math-embed.service` del paso 7:

```
sudo systemctl daemon-reload
sudo systemctl enable --now math-llm math-embed
systemctl is-active math-llm math-embed    # active active
free -h                                    # ~2.5 Gi libres
```

## Paso 8: Repo + smoke test

```
cd ~ && git clone https://github.com/fajnykonrad/vectorsr3.git
cd vectorsr3
mkdir -p results
python3 predict.py --input data/sample_problems.jsonl --output results/smoke.csv
cat results/smoke.csv     # 5 filas, una letra A-E por fila, status ok
```

## Reportar al equipo de laptop

- [ ] IP de la placa y estado de ssh/adb
- [ ] `systemctl is-active math-llm math-embed` -> active
- [ ] salida de `cat results/smoke.csv`
- [ ] `free -h` con los servicios arriba

Con eso, el equipo de laptop puede lanzar `collect.py` (con port-forward o
adb push) y empezar el entrenamiento. NO hace falta `build_index.py` en la
placa: el índice llega hecho desde el laptop.

# MÉTODO FINAL — Cómo responde el copiloto (v. definitiva)

## Los dos modos, por la distribución del test

El sistema tiene **dos modos**, porque hay dos distribuciones posibles y
están medidas:

| Modo | Cuándo | Config | Accuracy medida |
|---|---|---|---|
| **M3KANG** | distribucion sesgada (D 25%) como M3Kang | heurísticas ON, calibración OFF | **27.8%** (562 cat+eng, en placa) |
| **JURADO** (uniform) | letras uniformes (20% c/u), como el demo oficial | heurísticas OFF, **calibración uniforme ON** | **~25-26%** esperado (25-26% en laptop; raw en placa 21%) |

El modo se elige con `--uniform` en predict.py/eval.py. Para el **test
oculto de las 12:00 se usa `--uniform`** (el jurado anuncia en su README
"every letter A–E correct 10 times").

## El flujo de una predicción (modo JURADO, el del test)

```
problema nuevo (texto + opciones OCR)
        |
        v
LLM 0.8B (grammar [A-E], temperature 0, seed 42)
        |
        v
probs = {A: ..., B: ..., C: ..., D: ..., E: ...}   <- log-probabilities
        |
        v
CALIBRACION UNIFORME:
   q_L = p_L / suma(p)                  <- marginal del modelo por letra
   score(L) = log p_L - 0.8 * log q_L   <- penaliza cada letra por su exceso
   respuesta = argmax(score)
```

**Qué corrige la calibración**: el modelo dice D con probabilidad marginal
0.47 (debería ser 0.20 con letras uniformes) y C con 0.05. La calibración
divide cada letra por su exceso: el sesgo desaparece y las respuestas se
reparten casi uniforme — que es exactamente la distribución del test.

**Medición** (set de práctica del jurado, 100 problemas):
- raw: 20.0% → calibrado λ=0.8-1.0: **25-26%** (+5-6 puntos)
- Validez: no usa labels del demo para el fit (solo la margianl del modelo
  y el hecho público de letras uniformes); verificado con split half↔half
  (22-33%, siempre ≥ raw)

## Por qué NO heurísticas en el modo jurado

La mediana del valor de opciones ganaba en M3Kang (27.7% vs 22.8%) porque
M3Kang concentra la respuesta en la mediana. El set del jurado la reparte
uniforme entre los ranks (medido: 20/26/15/20/19%) — la mediana ahí da 14%
(peor que azar). El prior por nivel viene del sesgo D de M3Kang: también
fuera. Ambas capas se desactivan con `--uniform` y el pipeline lo tiene
medido y documentado (`analyze_ranks.py`, `tune_policy2.py`).

## Operación del test de las 12:00

1. Placa reiniciada y con solo los servicios systemd arriba (sin procesos
   manuales cerca: los 9 "Connection refused" del demo fueron un reinicio)
2. Comando que ejecutará el jurado:
   `python3 predict.py --input <test>.jsonl --output predictions.csv --uniform`
3. Fallbacks garantizados: si un problema tarda >60 s o falla, responde D
   (timeout ya visto: 2/100 en el demo, con la placa recién arrancada deben
   ser 0-1)
4. Determinista: temperature 0, seed 42, sin red

## Las dos historias para el pitch

1. **M3Kang (27.8% vs piso 23.1%)**: "medimos 8 configuraciones; la
   ganadora no fue más IA sino saber cuándo NO usarla: heurísticas clásicas
   donde cada una vence al modelo (medido), modelo donde él vence"
2. **Jury set (25-26% vs piso 20%)**: "su distribución es otra y lo
   detectamos con su set de práctica un día antes: desactivamos lo que no
   transfiere y recalibrar el marginal del modelo a uniforme — mismo
   método, decisión distinta, por datos"

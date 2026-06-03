# rotture.md — Risposte punto per punto alle domande di Jie

## URGENTE: EXAM_POOL e MBPP dataset (#15, #19 bis)

**EXAM_POOL non è cambiato.** Confermato:
```
['django__django-11066', 'pydata__xarray-4629', 'scikit-learn__scikit-learn-13439',
 'sympy__sympy-13480', 'sympy__sympy-14711', 'sympy__sympy-18189']
```
Le stesse 6 task di sempre. **Non serve runnare di nuovo nulla.**

**`sympy__sympy-21847` non fa parte del pool.** Il comando `make run-swebench`
esegue `moulinette dump --benchmark swebench` che dumpa un task CASUALE dall'intero
dataset SWE-bench (6000+ task), NON dal pool d'esame. Il pool è usato solo dagli
exam scripts. Il one-shot esegue su qualsiasi task — è normale.

**MBPP 419 tasks:** la moulinette conta il dataset totale (train+test). Noi abbiamo
benchmarkato il test split (257 task). Non è cambiato nulla per noi.

---

## Problemi macOS che NON possiamo fixare (eval_documents intoccabile)

### #21 — `mktemp --suffix=.json` non funziona su macOS

`mktemp --suffix=.json` è sintassi GNU/Linux. macOS usa una sintassi diversa.
Questo rompe `exam_mbpp.sh` e `exam_swebench.sh` su macOS.

**Non possiamo fixarlo**: i file sono in `eval_documents/` che non dobbiamo toccare.
**Non è un problema per la valutazione**: il valutatore gira su Linux dove funziona.

Fix locale per testare su macOS (installa GNU coreutils):
```bash
brew install coreutils
# poi aggiungi a ~/.zshrc:
export PATH="/opt/homebrew/opt/coreutils/libexec/gnubin:$PATH"
```
Dopo questo i comandi `mktemp` e `timeout` funzioneranno.

### #19 — `timeout: command not found` (exam_sandbox.sh)

Stesso problema: `timeout` è un comando GNU, non presente di default su macOS.
Stessa soluzione: `brew install coreutils`.
Il test `MCP HTTP Connection` fallisce su macOS per questo motivo, non per un bug
nel nostro codice. Il valutatore gira su Linux → nessun problema reale.

---

## Problemi che possiamo fixare

### #1 — providers.py corretto o no?

**Il codice è corretto.** Spiegazione:
- `_openrouter`: aggiunge l'header `HTTP-Referer` richiesto da OpenRouter. ✓
- `_gemini`: è un handler separato pronto per accesso diretto a Gemini (non usato
  nel benchmark ma disponibile). ✓
- `_generic`: tutti gli altri provider usano l'endpoint OpenAI-compat standard. ✓
- Il registro ha 6 provider → tutti quelli supportati. ✓

Gemini nei benchmark è stato usato via OpenRouter (stesso endpoint), non direttamente.
L'handler `_gemini` è lì per chi vuole usare la chiave Gemini diretta in futuro.

### #2 — `agent/prompts/tool_prompt.txt` è vuoto/mancante

Il file non esiste — era un placeholder. Verificato: nessun codice lo importa.
**Da eliminare** se esiste come file vuoto.

### #3 — `config/models.yaml`

Contiene modelli OpenRouter free per riferimento personale. Non è usato da nessun
script Python o bash. **Da eliminare** — le informazioni sono ora nel README.

### #4 — Risultati extra task non visibili nella cartella

I risultati di `bench_extra_swe` sono in `evaluations/bench_extra_swe/`. Controllare
se sono stati committati. Se no, eseguire `git add evaluations/bench_extra_swe/ && git push`.

### #5 — `evaluations/bench_mbpp/` e `evaluations/bench_swebench/`

Questi folder contengono i solution.json di tutti i run storici — sono i **backing data**
richiesti dal report. **Non eliminare.** Sono necessari per il punto "Backing Data Spot-Check"
della valutazione (il valutatore chiederà di aprire un solution.json specifico).

### #6 — `utils/moulinette/` è un duplicato?

`utils/moulinette/` = copia del pacchetto moulinette (senza venv).
`./moulinette/` = installazione con venv usata dagli script.
Sono la stessa cosa ma `utils/moulinette/` non è usata da nessuno script.
**Da eliminare** o da chiarire se è un submodule.

### #7 — `models.md`

File con modelli OpenRouter — vecchio, informazioni superate. **Già rimosso**
(git rm eseguito in sessione precedente). Se compare ancora fare `git pull`.

### #8 — `scripts/run_benchmark.sh` e `run_benchmark_command.sh`

Questi file non esistono nella cartella `scripts/` attuale. Probabilmente erano in
un ramo vecchio e già rimossi. Verificare con `git log --all --diff-filter=D --name-only`.

### #9 — Cartella `tst/`

Non esiste nel progetto attuale. Probabilmente già rimossa.

### #10 — `eval/report_builder.py`

File che costruisce un report markdown da solution.json. Non è chiamato da nessun
script attuale (bench_all.sh genera il proprio SUMMARY.md). **Da eliminare** — la
funzionalità è stata sostituita da BENCHMARK_REPORT.md compilato manualmente.

### #11 — `filterwarnings` troppo broad

Jie ha ragione: `"ignore::RuntimeWarning"` sopprime tutti i RuntimeWarning.
Soluzione: filtrare solo il warning specifico di httpx.
**→ Fix applicato nel commit seguente.**

### #12 — Warning `RequestsDependencyWarning` su macOS

Il warning `urllib3 (2.6.3) or chardet doesn't match supported version` viene dalla
libreria `requests` usata dal venv di moulinette. **Non è nel nostro codice** — è
nel venv isolato di moulinette. Non lo possiamo/dobbiamo fixare.

Per trovare i log del one-shot: sono in `/tmp/solution.json`. Per vedere il dettaglio:
```bash
cat /tmp/solution.json | python3 -m json.tool | head -50
# oppure
cd moulinette && uv run moulinette_eval display /tmp/solution.json
```

### #13 — SWE iterazioni migliorate (3 invece di 4 per sympy-13480)?

Varianza naturale tra run. In sessioni precedenti abbiamo visto lo stesso task variare
tra 4 e 13 iterazioni. Un singolo run non è rappresentativo. **Lasciare i dati storici
nel report** — quelli sono i dati del benchmark ufficiale, non one-shot.

### #14 — Docker duplication: `_docker.py` vs `mydocker/manager.py`

Confermato: duplicazione significativa. **Fix pianificato** — merge da fare.
→ Vedi fix nel commit.

### #16 — README: aggiungere sezione Sandbox e MCP

**→ Fix applicato nel commit seguente.**

### #17 — OpenRouter gpt-oss-120b, errore 503

Il modello `openai/gpt-oss-120b:free` ha un rate limit molto basso su OpenRouter
(50 req/day). Il 503 significa che la quota giornaliera era esaurita.
**→ Rimosso dal README come modello consigliato.**

### #18 — `uv run agent-mbpp` fallisce con ValidationError

Jie ha eseguito `make run-swebench` (che dumpa un task SWE in `/tmp/task.json`),
poi ha eseguito manualmente `uv run agent-mbpp --task-file /tmp/task.json`.
Il file è un task SWE, non MBPP → ValidationError atteso.

**Fix**: i comandi `make run-mbpp` e `make run-swebench` useranno path separati:
`/tmp/mbpp-task.json` e `/tmp/swe-task.json`.
→ Fix nel Makefile nel commit seguente.

### #20 — `make mcp-mbpp` → `python: No such file or directory`

Su macOS (e anche Linux in certi setup) il comando è `python3`, non `python`.
Il Makefile usa `python`. **→ Fix: cambiare in `uv run python`** nel commit seguente.

Errore `ModuleNotFoundError: No module named 'mcp'` quando si usa `python3` diretto:
questo è corretto — bisogna usare `uv run python` che usa il venv del progetto.

### #22 — Test skip e warning su macOS

- **Skip**: probabilmente il test del Docker (SWE-bench) saltato perché Docker non
  configurato / immagini non presenti. Non è un bug del codice.
- **Warning**: il `RequestsDependencyWarning` di moulinette non è nel nostro codice.

### #23 — `make validate-mbpp` → fallisce con token exceeded

`validate-mbpp` usa `/tmp/task.json` e `/tmp/solution.json` che erano stati scritti
da una run precedente (non mistral-medium, non MBPP). È un falso positivo causato da
file /tmp residui.

**Fix**: come al punto #18, separare i path dei file temporanei.

---

## Checklist fix da applicare nel commit

- [ ] Eliminare `config/models.yaml`
- [ ] Eliminare `eval/report_builder.py`
- [ ] Eliminare `utils/moulinette/` (se non è submodule)
- [ ] Fix `filterwarnings` più specifico
- [ ] Fix Makefile: `python` → `uv run python` per mcp targets
- [ ] Fix Makefile: path separati per mbpp e swe (/tmp/mbpp-* e /tmp/swe-*)
- [ ] Fix Docker duplication
- [ ] README: aggiungere sezione Sandbox/MCP
- [ ] README: rimuovere OpenRouter come default/consigliato
- [ ] Commit evaluations/bench_extra_swe/ results

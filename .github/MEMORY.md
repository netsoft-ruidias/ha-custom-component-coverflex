# Coverflex Integration — Technical Memory

> Este ficheiro serve de memória técnica para IAs assistentes e developers futuros.
> Contém toda a informação necessária para entender, manter e evoluir esta integração.

---

## Contexto

**Coverflex** é uma plataforma de benefícios para colaboradores (https://my.coverflex.com).  
Esta integração expõe os saldos das carteiras (pockets) e movimentos de um utilizador como sensores no Home Assistant.

A API não é pública nem documentada — foi descoberta por engenharia reversa do bundle JavaScript do frontend web em:  
`https://my.coverflex.com/_expo/static/js/web/index-*.js`

---

## API — Endpoints

| Constante                  | URL                             | Método |
| -------------------------- | ------------------------------- | ------ |
| `API_LOGIN_URL`            | `.../sessions`                  | POST   |
| `API_TRUST_USER_AGENT_URL` | `.../sessions/trust-user-agent` | POST   |
| `API_RENEW_URL`            | `.../sessions/renew`            | POST   |
| `API_CARD_URL`             | `.../card`                      | GET    |
| `API_POCKETS_URL`          | `.../pockets`                   | GET    |
| `API_MOVEMENTS_URL`        | `.../movements`                 | GET    |

Base URL: `https://menhir-api.coverflex.com/api/employee`  
Definida em `custom_components/coverflex/const.py` como `API_BASE_URL`.

---

## Headers Obrigatórios

Todos os pedidos **devem** incluir os seguintes headers, caso contrário a API rejeita com HTTP 4xx:

```
Accept: application/json, text/plain, */*
Content-Type: application/json
x-coverflex-channel: web
x-coverflex-language: en-GB
x-coverflex-version: 1.462.0
x-coverflex-rum-session-id: <uuid4 gerado por sessão>
```

> `x-coverflex-version` pode ficar desatualizado ao longo do tempo. Se a API começar a falhar,
> verificar a versão atual no bundle JS com:
>
> ```bash
> curl -s "https://my.coverflex.com/_expo/static/js/web/index-*.js" | grep -oP '"version":"\K[^"]+' | head -5
> ```
>
> e atualizar `API_VERSION` em `const.py`.

Implementado em `CoverflexAPI._base_headers()`.

---

## Fluxo de Autenticação

O fluxo tem **3 níveis de fallback**, por ordem de prioridade:

### Nível 1 — Renovação silenciosa via `refresh_token`

```
POST /sessions/renew
Authorization: Bearer <refresh_token>
Body: null

→ HTTP 201
{
  "data": {
    "access_token": "<novo JWT de ~30 min>",
    "refresh_token": "<novo JWT de ~7 dias>"
  }
}
```

- Não requer credenciais nem OTP.
- O `refresh_token` é rotativo — guardar sempre o novo valor devolvido.
- Se retornar erro (expirado, revogado), avançar para o Nível 2.
- Implementado em `CoverflexAPI.refresh_access_token(refresh_token)`.

---

### Nível 2 — Login com `user_agent_token` (sem OTP)

```
POST /sessions
Body: { "email": "...", "password": "...", "user_agent_token": "<JWT de ~90 dias>" }

→ HTTP 201
{ "token": "<access_token de ~30 min>" }
```

- Requer credenciais válidas.
- O `user_agent_token` identifica um dispositivo de confiança — se for válido, o servidor não pede OTP.
- Se retornar HTTP 202, o `user_agent_token` expirou ou foi revogado → avançar para o Nível 3.
- Implementado em `CoverflexAPI.login(username, password, user_agent_token=...)`.

---

### Nível 3 — Login com OTP (autenticação a dois factores)

#### Passo 3a — Iniciar login

```
POST /sessions
Body: { "email": "...", "password": "..." }

→ HTTP 202  ← significa que OTP é necessário
{
  "otp_channel": "sms",
  "phone_last_digits": "123"
}
```

O servidor envia um código de 6 dígitos por SMS para o número do utilizador.

#### ⚠️ Instrução para IA assistente

> Quando o código chega a este ponto e lança `OTPRequiredException`, a IA **NÃO deve tentar
> adivinhar nem gerar** o código OTP. A IA deve **parar e pedir ao Humano** que:
>
> 1. Verifique o telemóvel (SMS do número associado à conta Coverflex)
> 2. Forneça o código de 6 dígitos recebido
> 3. Introduza o código no prompt `"Enter the OTP code............: "`
>
> Só após o Humano fornecer o código é que o fluxo pode continuar.

#### Passo 3b — Verificar OTP

```
POST /sessions
Body: { "email": "...", "password": "...", "otp": "<6 dígitos>" }

→ HTTP 201
{ "token": "<access_token temporário>" }
```

#### Passo 3c — Obter tokens de confiança (trust)

Após obter o `access_token` via OTP, chamar imediatamente:

```
POST /sessions/trust-user-agent
Authorization: Bearer <access_token>
Body: null

→ HTTP 201
{
  "token": "<access_token renovado>",
  "refresh_token": "<JWT de ~7 dias>",
  "user_agent_token": "<JWT de ~90 dias>"
}
```

Guardar os três tokens persistentemente:

- `access_token` → usar imediatamente para chamadas API
- `refresh_token` → guardar em `.coverflex_refresh_token`
- `user_agent_token` → guardar em `.coverflex_device_token`

Implementado em `CoverflexAPI.get_trust_token(token)` — devolve um `dict` com as três chaves.

---

## Tokens — Resumo e Ciclo de Vida

| Token              | Ficheiro local             | Duração aprox. | Uso                                        |
| ------------------ | -------------------------- | -------------- | ------------------------------------------ |
| `access_token`     | não guardado               | ~30 minutos    | Bearer em todas as chamadas à API          |
| `refresh_token`    | `.coverflex_refresh_token` | ~7 dias        | Renovar `access_token` sem re-login        |
| `user_agent_token` | `.coverflex_device_token`  | ~90 dias       | Login sem OTP num dispositivo de confiança |

> Ambos os ficheiros locais estão em `.gitignore` — **nunca fazer commit** destes valores.

Quando o `refresh_token` expira, o fluxo cai para Nível 2.  
Quando o `user_agent_token` também expira, o Humano terá de fornecer um novo OTP (Nível 3).

---

## Problema Conhecido — `aiodns` / `pycares`

`pycares 5.0.1` é incompatível com `aiodns 3.2.0`, causando erro na resolução DNS assíncrona.  
**Workaround** no `example.py` e em qualquer script fora do Home Assistant:

```python
connector = aiohttp.TCPConnector(resolver=aiohttp.resolver.ThreadedResolver())
async with aiohttp.ClientSession(connector=connector) as session:
    ...
```

O Home Assistant gere a sua própria `ClientSession` internamente, pelo que este problema não afeta a integração em produção.

---

## Estrutura do Projeto

```
custom_components/coverflex/
  __init__.py          — Entry point da integração HA (setup, unload)
  api.py               — Cliente HTTP: CoverflexAPI (login, refresh, card, pockets, movements)
  config_flow.py       — Config flow do HA (UI de configuração)
  const.py             — Todas as constantes (URLs, headers, nomes de domínio)
  exceptions.py        — OTPRequiredException
  interfaces.py        — Modelos de dados: Card, Pocket, Transaction
  manifest.json        — Metadados da integração HA
  sensor.py            — Plataforma de sensores HA
  strings.json         — Strings de UI (inglês)
  translations/
    en.json            — Traduções inglês
    pt.json            — Traduções português

example.py             — Script de teste standalone (fora do HA)
.env                   — Credenciais locais (não em git): COVERFLEX_USERNAME, COVERFLEX_PASSWORD
.coverflex_device_token   — user_agent_token persistido (não em git)
.coverflex_refresh_token  — refresh_token persistido (não em git)
```

---

## Credenciais de Desenvolvimento (local)

Guardar num ficheiro `.env` na raiz do projecto (nunca em git):

```env
COVERFLEX_USERNAME=email@example.com
COVERFLEX_PASSWORD=a_tua_password
```

Carregar com `python-dotenv`:

```python
from dotenv import load_dotenv
load_dotenv()
username = os.getenv("COVERFLEX_USERNAME", "")
```

---

## Executar o Script de Teste

```bash
# Activar o ambiente virtual
source .venv/bin/activate

# Correr o script (lê .env automaticamente, pressionar Enter para usar valores do .env)
python example.py
```

Se o `refresh_token` for válido, o login é silencioso.  
Se não existir ou tiver expirado, tentará o `user_agent_token`.  
Se ambos falharem, pede o código OTP por SMS.

---

## Resposta da API — Estrutura de Dados

### `GET /card`

```json
{
  "id": "...",
  "holder_name": "Nome Apelido",
  "holder_company_name": "Empresa S.A.",
  "status": "active",
  "pan_last_digits": "1234",
  "activated_at": "2024-01-15T10:30:00Z",
  "expiration_date": "2026-01-31T00:00:00Z"
}
```

> `activated_at` e `expiration_date` podem ser `null` — o código trata este caso.

### `GET /pockets`

```json
[
  {
    "id": "pocket-uuid",
    "type": "meal",
    "balance": { "amount": 4250, "currency": "EUR" }
  }
]
```

> `balance.amount` está em cêntimos — dividir por 100 para obter o valor em euros.  
> Existem múltiplas pockets (ex: `meal`, `transport`, `health`, `flex`).

### `GET /movements?pocket_id=...&per_page=10`

```json
[
  {
    "executed_at": "2024-05-01T12:00:00Z",
    "description": "Restaurante XYZ",
    "amount": { "amount": -1200, "currency": "EUR" },
    "is_debit": true
  }
]
```

---

## Fase HA — Estado Actual e Pendente

| Componente       | Estado      | Notas                                                                           |
| ---------------- | ----------- | ------------------------------------------------------------------------------- |
| `api.py`         | ✅ Completo | Login, OTP, trust, refresh, card, pockets, movements                            |
| `const.py`       | ✅ Completo | Todos os URLs e constantes                                                      |
| `interfaces.py`  | ✅ Completo | Card, Pocket, Transaction com None handling                                     |
| `exceptions.py`  | ✅ Completo | OTPRequiredException                                                            |
| `example.py`     | ✅ Completo | Script de teste com fluxo completo de 3 níveis                                  |
| `config_flow.py` | ❌ Pendente | Deve guardar `user_agent_token` e `refresh_token` em `config_entry.data`        |
| `sensor.py`      | ❌ Pendente | Deve criar um sensor por pocket (iterar `get_balances()`)                       |
| `__init__.py`    | ❌ Pendente | Deve usar `refresh_access_token` em cada ciclo de update; reauth flow se falhar |

### Plano para o HA

1. **`config_flow.py`**: No setup inicial pedir credenciais → fazer login com OTP → guardar `{ username, password, user_agent_token, refresh_token }` em `config_entry.data`.

2. **`__init__.py`** (`async_update`):

   ```
   1. Tentar refresh_access_token(refresh_token) → se OK, usar novo access_token
   2. Se falhar, tentar login(username, password, user_agent_token=user_agent_token)
   3. Se ambos falharem → disparar HA reauth flow (pede OTP ao utilizador via UI do HA)
   ```

3. **`sensor.py`**: Criar um sensor `CoverflexPocketSensor` por entrada em `get_balances()`, com `unique_id = f"{username}_{pocket.type}"`.

---

## Descoberta da API

Para descobrir novos endpoints ou confirmar alterações à API, inspecionar o bundle JS:

```bash
# Encontrar o bundle actual
curl -s "https://my.coverflex.com" | grep -oP 'index-[a-f0-9]+\.js'

# Pesquisar endpoints
curl -s "https://my.coverflex.com/_expo/static/js/web/index-HASH.js" \
  | grep -oP 'SESSIONS:\{[^}]+\}'

# Pesquisar estrutura de pedidos (ex: renew)
curl -s "https://my.coverflex.com/_expo/static/js/web/index-HASH.js" \
  | grep -oP '.{0,300}sessions/renew.{0,300}'
```

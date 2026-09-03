"""
Servidor Leblon Store - Flask + Baserow
-------------------------------------
Rodar:
    pip install -r requirements.txt
    python servidor.py

Abre em: http://localhost:5000
"""

import os
import requests
import base64
from flask import Flask, jsonify, request, send_from_directory, session
from flask_cors import CORS
from functools import wraps
from datetime import datetime
from io import BytesIO
import json
from dotenv import load_dotenv

# Carregar variáveis de ambiente do .env
load_dotenv()

app = Flask(__name__, static_folder=".", static_url_path="")
app.secret_key = os.getenv("SECRET_KEY", "leblon_store_secret_key_2024")
CORS(app, supports_credentials=True)

BASEROW_URL = "https://api.baserow.io/api/database/rows/table"
BASEROW_UPLOAD_URL = "https://api.baserow.io/api/user-files/upload-file/"

# Tokens carregados do .env
TOKENS = {
    "produtos": os.getenv("TOKEN_PRODUTOS"),
    "produtos_18": os.getenv("TOKEN_PRODUTOS_18"),
    "login": os.getenv("TOKEN_LOGIN"),
    "pedidos": os.getenv("TOKEN_PEDIDOS"),
    "login_admin": os.getenv("TOKEN_LOGIN_ADMIN"),
    "streaming": os.getenv("TOKEN_STREAMING"),
}

TABELAS = {
    "produtos": 1090902,
    "produtos_18": 1173585,
    "login": 1169585,
    "pedidos": 1169586,
    "login_admin": 1173659,
    "streaming": 1173710,
}

DATABASES = {
    "principal": 500516,
    "login": 542053,
    "pedidos": 542054,
    "dezoito": 544183,
    "login_admin": 544236,
    "streaming": 544279,
}

# Chave PIX usada na tela de pagamento
CHAVE_PIX = os.getenv("CHAVE_PIX", "615add06-24f5-421f-8ac1-cc3e0a52f60c")


def headers(chave):
    return {
        "Authorization": f"Token {TOKENS[chave]}",
        "Content-Type": "application/json",
    }


def headers_upload(chave):
    return {
        "Authorization": f"Token {TOKENS[chave]}",
    }


def listar_linhas(chave, size=200, filters=None):
    """Le todas as linhas de uma tabela do Baserow."""
    url = f"{BASEROW_URL}/{TABELAS[chave]}/?user_field_names=true&size={size}"

    if filters:
        for key, value in filters.items():
            url += f"&{key}={value}"

    linhas = []
    while url:
        try:
            r = requests.get(url, headers=headers(chave), timeout=30)
            r.raise_for_status()
            data = r.json()
            linhas.extend(data.get("results", []))
            url = data.get("next")
        except requests.exceptions.RequestException as e:
            print(f"Erro ao listar linhas da tabela {chave}: {e}")
            return []
    return linhas


def criar_linha(chave, payload):
    url = f"{BASEROW_URL}/{TABELAS[chave]}/?user_field_names=true"
    try:
        print(f"📤 Criando linha na tabela {chave} (ID: {TABELAS[chave]})")
        print(f"📦 Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        r = requests.post(url, headers=headers(chave), json=payload, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao criar linha na tabela {chave}: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"📄 Resposta: {e.response.text}")
        raise


def atualizar_linha(chave, linha_id, payload):
    """Atualiza uma linha existente no Baserow."""
    url = f"{BASEROW_URL}/{TABELAS[chave]}/{linha_id}/?user_field_names=true"
    try:
        print(f"📤 Atualizando linha {linha_id} na tabela {chave}")
        print(f"📦 Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
        r = requests.patch(url, headers=headers(chave), json=payload, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao atualizar linha {linha_id} na tabela {chave}: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"📄 Resposta: {e.response.text}")
        raise


def deletar_linha(chave, linha_id):
    """Deleta uma linha do Baserow."""
    url = f"{BASEROW_URL}/{TABELAS[chave]}/{linha_id}/"
    try:
        r = requests.delete(url, headers=headers(chave), timeout=30)
        r.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        print(f"Erro ao deletar linha {linha_id} na tabela {chave}: {e}")
        raise


def detectar_tipo_imagem(imagem_bytes):
    """Detecta o tipo da imagem a partir dos bytes sem usar imghdr."""
    if imagem_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    elif imagem_bytes.startswith(b'\xff\xd8\xff'):
        return 'jpg'
    elif imagem_bytes.startswith(b'GIF87a') or imagem_bytes.startswith(b'GIF89a'):
        return 'gif'
    elif imagem_bytes.startswith(b'RIFF') and len(imagem_bytes) > 12 and imagem_bytes[8:12] == b'WEBP':
        return 'webp'
    elif imagem_bytes.startswith(b'BM'):
        return 'bmp'
    elif imagem_bytes.startswith(b'%PDF'):
        return 'pdf'
    else:
        return 'png'


def upload_imagem_para_baserow(imagem_base64, chave):
    """
    Faz upload de uma imagem Base64 para o Baserow usando multipart/form-data.
    Retorna o objeto completo da imagem no formato que o Baserow espera.
    """
    try:
        if ',' in imagem_base64:
            imagem_base64 = imagem_base64.split(',')[1]

        imagem_bytes = base64.b64decode(imagem_base64)
        tipo = detectar_tipo_imagem(imagem_bytes)

        arquivo = BytesIO(imagem_bytes)
        arquivo.seek(0)

        files = {
            'file': (f'produto.{tipo}', arquivo, f'image/{tipo}')
        }

        print(f"📤 Fazendo upload da imagem para o Baserow...")
        r = requests.post(
            BASEROW_UPLOAD_URL,
            files=files,
            headers=headers_upload(chave),
            timeout=30
        )
        r.raise_for_status()
        data = r.json()

        print(f"✅ Imagem enviada com sucesso!")
        return data
    except Exception as e:
        print(f"❌ Erro no upload da imagem: {e}")
        return None


def primeiro_arquivo(valor):
    """Campo 'imagem' do Baserow e uma lista de arquivos."""
    if isinstance(valor, list) and valor:
        primeiro = valor[0]
        if isinstance(primeiro, dict):
            return primeiro.get("url") or primeiro.get("thumbnails", {}).get("large", {}).get("url")
        return primeiro
    if isinstance(valor, str):
        return valor or None
    return None


def normalizar_produto(row, adulto=False):
    return {
        "id": row.get("id"),
        "nome": row.get("nome") or row.get("Nome") or "Sem nome",
        "descricao": row.get("descrição") or row.get("descricao") or row.get("Descrição") or "",
        "preco": row.get("preço") or row.get("preco") or row.get("Preço") or "0",
        "imagem": primeiro_arquivo(row.get("imagem") or row.get("Imagem")),
        "categoria": (row.get("categoria") or row.get("Categoria") or ("+18" if adulto else "Geral")),
        "adulto": adulto,
    }


def normalizar_streaming(row):
    """Normaliza um item de streaming."""
    return {
        "id": row.get("id"),
        "nome": row.get("nome") or "Sem nome",
        "descricao": row.get("descrição") or "",
        "preco": row.get("preço") or "0",
        "imagem": primeiro_arquivo(row.get("imagem")),
        "tipo": row.get("tipo") or "Streaming",
        "categoria": row.get("categoria") or "Geral",
    }


def login_gerente_required(f):
    """Decorator para proteger rotas do gerente."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('gerente_logado'):
            return jsonify({"erro": "Acesso não autorizado. Faça login como gerente."}), 401
        return f(*args, **kwargs)
    return decorated_function


# ============================================================
# ROTAS PUBLICAS
# ============================================================

@app.get("/")
def index():
    return send_from_directory(".", "index.html")


@app.get("/gerente.html")
def gerente():
    return send_from_directory(".", "gerente.html")


@app.get("/api/config")
def config():
    return jsonify({"chave_pix": CHAVE_PIX})


@app.get("/api/produtos")
def produtos():
    """?adulto=1 inclui produtos +18"""
    incluir18 = request.args.get("adulto") in ("1", "true", "sim")
    try:
        itens = [normalizar_produto(r) for r in listar_linhas("produtos")]
        if incluir18:
            itens += [normalizar_produto(r, adulto=True) for r in listar_linhas("produtos_18")]
        return jsonify(itens)
    except requests.HTTPError as e:
        return jsonify({"erro": "Falha ao carregar produtos", "detalhe": str(e)}), 502


@app.get("/api/produtos18")
def produtos18():
    try:
        return jsonify([normalizar_produto(r, adulto=True) for r in listar_linhas("produtos_18")])
    except requests.HTTPError as e:
        return jsonify({"erro": "Falha ao carregar produtos +18", "detalhe": str(e)}), 502


@app.get("/api/streaming")
def listar_streaming():
    """Lista todos os produtos de streaming."""
    try:
        itens = [normalizar_streaming(r) for r in listar_linhas("streaming")]
        return jsonify(itens)
    except requests.HTTPError as e:
        return jsonify({"erro": "Falha ao carregar streaming", "detalhe": str(e)}), 502


@app.post("/api/cadastro")
def cadastro():
    body = request.get_json(force=True) or {}
    nome = (body.get("nome") or "").strip()
    email = (body.get("email") or "").strip().lower()
    senha = (body.get("senha") or "").strip()

    if not nome or not email or not senha:
        return jsonify({"erro": "Preencha nome, email e senha"}), 400

    try:
        usuarios = listar_linhas("login")
        if any((u.get("email") or "").strip().lower() == email for u in usuarios):
            return jsonify({"erro": "Este email ja esta cadastrado"}), 409
        criar_linha("login", {"nome": nome, "email": email, "senha": senha})
        return jsonify({"ok": True, "usuario": {"nome": nome, "email": email}})
    except requests.HTTPError as e:
        return jsonify({"erro": "Falha ao cadastrar", "detalhe": str(e)}), 502


@app.post("/api/login")
def login():
    body = request.get_json(force=True) or {}
    email = (body.get("email") or "").strip().lower()
    senha = (body.get("senha") or "").strip()

    if not email or not senha:
        return jsonify({"erro": "Informe email e senha"}), 400

    try:
        for u in listar_linhas("login"):
            if (u.get("email") or "").strip().lower() == email and (u.get("senha") or "").strip() == senha:
                return jsonify({"ok": True, "usuario": {"nome": u.get("nome"), "email": u.get("email")}})
        return jsonify({"erro": "Email ou senha invalidos"}), 401
    except requests.HTTPError as e:
        return jsonify({"erro": "Falha ao entrar", "detalhe": str(e)}), 502


@app.get("/api/pedidos")
def listar_pedidos():
    """Lista pedidos - filtra por email se passado"""
    nome = (request.args.get("nome") or "").strip().lower()
    try:
        pedidos = listar_linhas("pedidos")
        itens = [
            {
                "id": p.get("id"),
                "nome": p.get("nome") or "",
                "pedido": p.get("pedido") or "",
                "status": p.get("status") or "Pendente",
                "data": p.get("data") or datetime.now().isoformat()
            }
            for p in pedidos
        ]
        if nome:
            itens = [p for p in itens if p["nome"].strip().lower() == nome]
        itens.reverse()
        return jsonify(itens)
    except requests.HTTPError as e:
        return jsonify({"erro": "Falha ao carregar pedidos", "detalhe": str(e)}), 502


@app.post("/api/pedidos")
def criar_pedido():
    body = request.get_json(force=True) or {}
    nome = (body.get("nome") or "").strip()
    pedido = (body.get("pedido") or "").strip()
    status = (body.get("status") or "Aguardando pagamento PIX").strip()
    data = body.get("data") or datetime.now().isoformat()

    if not nome or not pedido:
        return jsonify({"erro": "Pedido invalido"}), 400

    try:
        criado = criar_linha("pedidos", {
            "nome": nome,
            "pedido": pedido,
            "status": status,
            "data": data
        })
        return jsonify({"ok": True, "id": criado.get("id"), "status": status})
    except requests.HTTPError as e:
        return jsonify({"erro": "Falha ao salvar pedido", "detalhe": str(e)}), 502


# ============================================================
# ROTAS DO GERENTE - LOGIN
# ============================================================

@app.post("/api/gerente/login")
def gerente_login():
    """Login do gerente - verifica na tabela login_admin do Baserow"""
    body = request.get_json(force=True) or {}
    usuario = (body.get("email") or body.get("usuario") or "").strip()
    senha = (body.get("senha") or "").strip()

    if not usuario or not senha:
        return jsonify({"erro": "Informe usuário e senha"}), 400

    try:
        usuarios = listar_linhas("login_admin")

        for u in usuarios:
            u_usuario = (u.get("usuario") or "").strip()
            u_senha = (u.get("senha") or "").strip()

            if u_usuario == usuario and u_senha == senha:
                session['gerente_logado'] = True
                session['gerente_email'] = usuario
                session['gerente_nome'] = usuario
                session['gerente_codigo'] = u.get("codigo") or ""
                return jsonify({
                    "ok": True,
                    "usuario": {
                        "nome": usuario,
                        "email": usuario,
                        "codigo": session['gerente_codigo']
                    }
                })

        return jsonify({"erro": "Credenciais invalidas"}), 401
    except Exception as e:
        return jsonify({"erro": "Falha ao verificar credenciais", "detalhe": str(e)}), 502


@app.post("/api/gerente/logout")
def gerente_logout():
    """Logout do gerente."""
    session.pop('gerente_logado', None)
    session.pop('gerente_email', None)
    session.pop('gerente_nome', None)
    session.pop('gerente_codigo', None)
    return jsonify({"ok": True})


@app.get("/api/gerente/verificar")
def gerente_verificar():
    """Verifica se o gerente está logado."""
    if session.get('gerente_logado'):
        return jsonify({
            "ok": True,
            "email": session.get('gerente_email'),
            "nome": session.get('gerente_nome', 'Gerente'),
            "codigo": session.get('gerente_codigo', '')
        })
    return jsonify({"ok": False}), 401


# ============================================================
# ROTAS DO GERENTE - PEDIDOS
# ============================================================

@app.get("/api/gerente/pedidos")
@login_gerente_required
def gerente_listar_pedidos():
    """Lista todos os pedidos (visão do gerente)."""
    try:
        pedidos = listar_linhas("pedidos")
        itens = [
            {
                "id": p.get("id"),
                "nome": p.get("nome") or "",
                "pedido": p.get("pedido") or "",
                "status": p.get("status") or "Pendente",
                "data": p.get("data") or datetime.now().isoformat()
            }
            for p in pedidos
        ]
        itens.reverse()
        return jsonify(itens)
    except requests.HTTPError as e:
        return jsonify({"erro": "Falha ao carregar pedidos", "detalhe": str(e)}), 502


@app.put("/api/gerente/pedidos/<int:pedido_id>")
@login_gerente_required
def gerente_atualizar_pedido(pedido_id):
    """Atualiza o status de um pedido."""
    body = request.get_json(force=True) or {}
    status = body.get("status", "").strip()

    if not status:
        return jsonify({"erro": "Status é obrigatorio"}), 400

    status_validos = ["Pendente", "Confirmado", "Cancelado", "Aguardando pagamento PIX"]
    if status not in status_validos:
        return jsonify({"erro": f"Status invalido. Use: {', '.join(status_validos)}"}), 400

    try:
        atualizar_linha("pedidos", pedido_id, {"status": status})
        return jsonify({"ok": True, "id": pedido_id, "status": status})
    except requests.HTTPError as e:
        return jsonify({"erro": "Falha ao atualizar pedido", "detalhe": str(e)}), 502


@app.delete("/api/gerente/pedidos/<int:pedido_id>")
@login_gerente_required
def gerente_deletar_pedido(pedido_id):
    """Deleta um pedido (apenas para gerente)."""
    try:
        deletar_linha("pedidos", pedido_id)
        return jsonify({"ok": True})
    except requests.HTTPError as e:
        return jsonify({"erro": "Falha ao deletar pedido", "detalhe": str(e)}), 502


# ============================================================
# ROTAS DO GERENTE - PRODUTOS
# ============================================================

@app.post("/api/gerente/produtos")
@login_gerente_required
def gerente_criar_produto():
    """Cria um novo produto com upload de imagem."""
    body = request.get_json(force=True) or {}
    nome = (body.get("nome") or "").strip()
    descricao = (body.get("descricao") or "").strip()
    preco = (body.get("preco") or "0").strip()
    categoria = (body.get("categoria") or "Geral").strip()
    imagem_base64 = body.get("imagem") or ""
    adulto = body.get("adulto", False)

    if not nome:
        return jsonify({"erro": "Nome é obrigatorio"}), 400

    try:
        tabela = "produtos_18" if adulto else "produtos"
        payload = {
            "nome": nome,
            "descricao": descricao,
            "preco": preco,
            "categoria": categoria,
        }

        if imagem_base64 and imagem_base64.startswith('data:image'):
            chave_upload = "produtos_18" if adulto else "produtos"
            imagem_obj = upload_imagem_para_baserow(imagem_base64, chave_upload)
            if imagem_obj:
                payload["imagem"] = [imagem_obj]

        criado = criar_linha(tabela, payload)
        return jsonify({"ok": True, "id": criado.get("id")})
    except requests.HTTPError as e:
        return jsonify({"erro": "Falha ao criar produto", "detalhe": str(e)}), 502
    except Exception as e:
        return jsonify({"erro": f"Erro ao salvar produto: {str(e)}"}), 500


@app.put("/api/gerente/produtos/<int:produto_id>")
@login_gerente_required
def gerente_atualizar_produto(produto_id):
    """Atualiza um produto existente com upload de imagem."""
    body = request.get_json(force=True) or {}
    nome = (body.get("nome") or "").strip()
    descricao = (body.get("descricao") or "").strip()
    preco = (body.get("preco") or "0").strip()
    categoria = (body.get("categoria") or "Geral").strip()
    imagem_base64 = body.get("imagem") or ""
    adulto = body.get("adulto", False)

    if not nome:
        return jsonify({"erro": "Nome é obrigatorio"}), 400

    try:
        tabela = "produtos_18" if adulto else "produtos"
        payload = {
            "nome": nome,
            "descricao": descricao,
            "preco": preco,
            "categoria": categoria,
        }

        if imagem_base64 and imagem_base64.startswith('data:image'):
            chave_upload = "produtos_18" if adulto else "produtos"
            imagem_obj = upload_imagem_para_baserow(imagem_base64, chave_upload)
            if imagem_obj:
                payload["imagem"] = [imagem_obj]
        elif not imagem_base64:
            payload["imagem"] = None

        atualizar_linha(tabela, produto_id, payload)
        return jsonify({"ok": True, "id": produto_id})
    except requests.HTTPError as e:
        return jsonify({"erro": "Falha ao atualizar produto", "detalhe": str(e)}), 502
    except Exception as e:
        return jsonify({"erro": f"Erro ao salvar produto: {str(e)}"}), 500


@app.delete("/api/gerente/produtos/<int:produto_id>")
@login_gerente_required
def gerente_deletar_produto(produto_id):
    """Deleta um produto."""
    try:
        try:
            deletar_linha("produtos", produto_id)
            return jsonify({"ok": True})
        except:
            pass

        try:
            deletar_linha("produtos_18", produto_id)
            return jsonify({"ok": True})
        except:
            pass

        return jsonify({"erro": "Produto não encontrado"}), 404
    except requests.HTTPError as e:
        return jsonify({"erro": "Falha ao deletar produto", "detalhe": str(e)}), 502


# ============================================================
# ROTAS DO GERENTE - STREAMING
# ============================================================

@app.get("/api/gerente/streaming")
@login_gerente_required
def gerente_listar_streaming():
    """Lista todos os itens de streaming (visão do gerente)."""
    try:
        itens = [normalizar_streaming(r) for r in listar_linhas("streaming")]
        return jsonify(itens)
    except requests.HTTPError as e:
        return jsonify({"erro": "Falha ao carregar streaming", "detalhe": str(e)}), 502


@app.post("/api/gerente/streaming")
@login_gerente_required
def gerente_criar_streaming():
    """Cria um novo item de streaming."""
    body = request.get_json(force=True) or {}
    nome = (body.get("nome") or "").strip()
    descricao = (body.get("descricao") or "").strip()
    preco = (body.get("preco") or "0").strip()
    tipo = (body.get("tipo") or "Streaming").strip()
    categoria = (body.get("categoria") or "Geral").strip()
    imagem_base64 = body.get("imagem") or ""

    if not nome:
        return jsonify({"erro": "Nome é obrigatorio"}), 400

    try:
        payload = {
            "nome": nome,
            "descrição": descricao,
            "preço": preco,
            "tipo": tipo,
            "categoria": categoria,
        }

        if imagem_base64 and imagem_base64.startswith('data:image'):
            imagem_obj = upload_imagem_para_baserow(imagem_base64, "streaming")
            if imagem_obj:
                payload["imagem"] = [imagem_obj]

        criado = criar_linha("streaming", payload)
        return jsonify({"ok": True, "id": criado.get("id")})
    except requests.HTTPError as e:
        return jsonify({"erro": "Falha ao criar streaming", "detalhe": str(e)}), 502
    except Exception as e:
        return jsonify({"erro": f"Erro ao salvar streaming: {str(e)}"}), 500


@app.put("/api/gerente/streaming/<int:item_id>")
@login_gerente_required
def gerente_atualizar_streaming(item_id):
    """Atualiza um item de streaming."""
    body = request.get_json(force=True) or {}
    nome = (body.get("nome") or "").strip()
    descricao = (body.get("descricao") or "").strip()
    preco = (body.get("preco") or "0").strip()
    tipo = (body.get("tipo") or "Streaming").strip()
    categoria = (body.get("categoria") or "Geral").strip()
    imagem_base64 = body.get("imagem") or ""

    if not nome:
        return jsonify({"erro": "Nome é obrigatorio"}), 400

    try:
        payload = {
            "nome": nome,
            "descrição": descricao,
            "preço": preco,
            "tipo": tipo,
            "categoria": categoria,
        }

        if imagem_base64 and imagem_base64.startswith('data:image'):
            imagem_obj = upload_imagem_para_baserow(imagem_base64, "streaming")
            if imagem_obj:
                payload["imagem"] = [imagem_obj]
        elif not imagem_base64:
            payload["imagem"] = None

        atualizar_linha("streaming", item_id, payload)
        return jsonify({"ok": True, "id": item_id})
    except requests.HTTPError as e:
        return jsonify({"erro": "Falha ao atualizar streaming", "detalhe": str(e)}), 502
    except Exception as e:
        return jsonify({"erro": f"Erro ao salvar streaming: {str(e)}"}), 500


@app.delete("/api/gerente/streaming/<int:item_id>")
@login_gerente_required
def gerente_deletar_streaming(item_id):
    """Deleta um item de streaming."""
    try:
        deletar_linha("streaming", item_id)
        return jsonify({"ok": True})
    except requests.HTTPError as e:
        return jsonify({"erro": "Falha ao deletar streaming", "detalhe": str(e)}), 502


# ============================================================
# ROTAS DO GERENTE - USUÁRIOS
# ============================================================

@app.get("/api/gerente/usuarios")
@login_gerente_required
def gerente_listar_usuarios():
    """Lista todos os usuários (das tabelas login e login_admin)."""
    try:
        usuarios_normal = listar_linhas("login")
        usuarios_admin = listar_linhas("login_admin")

        todos = []
        for u in usuarios_normal:
            todos.append({
                "id": u.get("id"),
                "nome": u.get("nome") or "",
                "email": u.get("email") or "",
                "senha": u.get("senha") or "",
                "tipo": "cliente",
                "tabela": "login"
            })
        for u in usuarios_admin:
            todos.append({
                "id": u.get("id"),
                "nome": u.get("usuario") or "",
                "email": u.get("usuario") or "",
                "senha": u.get("senha") or "",
                "tipo": "admin",
                "codigo": u.get("codigo") or "",
                "tabela": "login_admin"
            })
        return jsonify(todos)
    except requests.HTTPError as e:
        return jsonify({"erro": "Falha ao carregar usuarios", "detalhe": str(e)}), 502


@app.post("/api/gerente/usuarios")
@login_gerente_required
def gerente_criar_usuario():
    """Cria um novo usuário."""
    body = request.get_json(force=True) or {}
    nome = (body.get("nome") or "").strip()
    email = (body.get("email") or "").strip().lower()
    senha = (body.get("senha") or "").strip()
    tipo = (body.get("tipo") or "cliente").strip().lower()

    if not email or not senha:
        return jsonify({"erro": "Email e senha são obrigatorios"}), 400

    try:
        tabela = "login_admin" if tipo == "admin" else "login"

        if tipo == "admin":
            payload = {"usuario": email, "senha": senha, "codigo": nome}
        else:
            payload = {"nome": nome, "email": email, "senha": senha}

        criado = criar_linha(tabela, payload)
        return jsonify({"ok": True, "id": criado.get("id")})
    except requests.HTTPError as e:
        return jsonify({"erro": "Falha ao criar usuario", "detalhe": str(e)}), 502


@app.put("/api/gerente/usuarios/<int:usuario_id>")
@login_gerente_required
def gerente_atualizar_usuario(usuario_id):
    """Atualiza um usuário."""
    body = request.get_json(force=True) or {}
    nome = (body.get("nome") or "").strip()
    email = (body.get("email") or "").strip().lower()
    senha = (body.get("senha") or "").strip()
    tipo = (body.get("tipo") or "cliente").strip().lower()

    try:
        admin = listar_linhas("login_admin")
        for u in admin:
            if u.get("id") == usuario_id:
                payload = {"usuario": email, "codigo": nome}
                if senha:
                    payload["senha"] = senha
                atualizar_linha("login_admin", usuario_id, payload)
                return jsonify({"ok": True})

        normal = listar_linhas("login")
        for u in normal:
            if u.get("id") == usuario_id:
                payload = {"nome": nome, "email": email}
                if senha:
                    payload["senha"] = senha
                atualizar_linha("login", usuario_id, payload)
                return jsonify({"ok": True})

        return jsonify({"erro": "Usuario nao encontrado"}), 404
    except requests.HTTPError as e:
        return jsonify({"erro": "Falha ao atualizar usuario", "detalhe": str(e)}), 502


@app.delete("/api/gerente/usuarios/<int:usuario_id>")
@login_gerente_required
def gerente_deletar_usuario(usuario_id):
    """Deleta um usuário."""
    try:
        try:
            deletar_linha("login_admin", usuario_id)
            return jsonify({"ok": True})
        except:
            pass

        try:
            deletar_linha("login", usuario_id)
            return jsonify({"ok": True})
        except:
            pass

        return jsonify({"erro": "Usuario nao encontrado"}), 404
    except requests.HTTPError as e:
        return jsonify({"erro": "Falha ao deletar usuario", "detalhe": str(e)}), 502


# ============================================================
# ROTAS DO GERENTE - ESTATISTICAS
# ============================================================

@app.get("/api/gerente/estatisticas")
@login_gerente_required
def gerente_estatisticas():
    """Retorna estatísticas para o painel do gerente."""
    try:
        pedidos = listar_linhas("pedidos")
        usuarios = listar_linhas("login")
        usuarios_admin = listar_linhas("login_admin")
        produtos_normais = listar_linhas("produtos")
        produtos_18 = listar_linhas("produtos_18")
        streaming = listar_linhas("streaming")

        total = len(pedidos)
        confirmados = sum(1 for p in pedidos if p.get("status", "").lower() == "confirmado")
        pendentes = sum(1 for p in pedidos if p.get("status", "").lower() in ["pendente", "aguardando pagamento pix"])
        cancelados = sum(1 for p in pedidos if p.get("status", "").lower() == "cancelado")

        return jsonify({
            "total": total,
            "confirmados": confirmados,
            "pendentes": pendentes,
            "cancelados": cancelados,
            "total_usuarios": len(usuarios) + len(usuarios_admin),
            "total_produtos": len(produtos_normais) + len(produtos_18),
            "total_streaming": len(streaming)
        })
    except requests.HTTPError as e:
        return jsonify({"erro": "Falha ao carregar estatisticas", "detalhe": str(e)}), 502


# ============================================================
# ROTA DE TESTE
# ============================================================

@app.get("/api/teste")
def teste():
    """Rota de teste para verificar se o servidor está funcionando."""
    return jsonify({
        "status": "ok",
        "mensagem": "Servidor Leblon Store está funcionando!",
        "versao": "1.0.0"
    })


# ============================================================
# INICIALIZAÇÃO
# ============================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print("\n" + "="*60)
    print("🚀 Servidor Leblon Store rodando!")
    print("="*60)
    print(f"📍 Local: http://localhost:{port}/")
    print(f"📍 Gerente: http://localhost:{port}/gerente.html")
    print(f"📍 Teste: http://localhost:{port}/api/teste")
    print("\n🔐 Login Admin (Baserow):")
    print("   Tabela: login_admin (ID: 1173659)")
    print("   Usuario: admin")
    print("   Senha: admin123")
    print("\n📊 Tabelas do Baserow:")
    print(f"   Produtos Normais: {TABELAS['produtos']}")
    print(f"   Produtos +18: {TABELAS['produtos_18']}")
    print(f"   Usuarios: {TABELAS['login']}")
    print(f"   Pedidos: {TABELAS['pedidos']}")
    print(f"   Login Admin: {TABELAS['login_admin']}")
    print(f"   Streaming: {TABELAS['streaming']}")
    print("="*60 + "\n")
    app.run(host="0.0.0.0", port=port, debug=True)
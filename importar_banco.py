import asyncio
import asyncpg
import os

async def restaurar_banco():
    # 1. Pega a URL do novo banco gerada pelo Replit
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("❌ Erro: Variável DATABASE_URL não encontrada! Verifique se você criou o banco na aba Database.")
        return

    print("🔄 Conectando ao banco de dados...")
    try:
        # 2. Conecta no PostgreSQL
        conn = await asyncpg.connect(database_url)

        print("📖 Lendo arquivo SQL...")
        # 3. Lê o conteúdo do seu arquivo .sql (ALTERE O NOME DO ARQUIVO AQUI EM BAIXO)
        with open('licitaim_database.sql', 'r') as arquivo:
            script_sql = arquivo.read()

        print("⚙️ Executando a restauração das tabelas e dados...")
        # 4. Executa o script no banco
        await conn.execute(script_sql)

        await conn.close()
        print("✅ Banco de dados restaurado com sucesso!")

    except Exception as e:
        print(f"❌ Ocorreu um erro: {e}")

# Executa a função
asyncio.run(restaurar_banco())
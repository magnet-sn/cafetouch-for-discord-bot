import os
import sys
import discord
from discord.ext import commands
from dotenv import load_dotenv

# .env ファイルから環境変数を読み込みます
load_dotenv()

# 環境変数の取得とエラーの確認を行います
try:
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
except Exception as e:
    print(f"エラー: {e}")
    sys.exit(1)

# Botの権限（Intents）の設定を行います
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!!', intents=intents)

# === 起動時の処理 ===
@bot.event
async def on_ready():
    print(f'ログイン完了: {bot.user}')
    # Discord上の「〇〇をプレイ中」のステータスの表示を設定をします
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="カフェタッチタイマー"))

    # 拡張機能（Cog）の読み込みを行います
    await load_extensions()

async def load_extensions():
    # 読み込むCogのファイルのパスを指定をします
    # cogsディレクトリの中の cafe.py を読み込みます
    extensions = ['cogs.cafe']
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            print(f"拡張機能の読み込みに成功: {ext}")
        except Exception as e:
            print(f"拡張機能の読み込みに失敗 {ext}: {e}")

# === 必須のコマンド ===
@bot.command()
async def ping(ctx):
    """Botの生存確認を行うためのコマンドです"""
    await ctx.send(f"Network latency : {round(bot.latency * 1000)}ms)")

if __name__ == '__main__':
    if DISCORD_TOKEN is None:
        print("DISCORD_TOKENが設定をされていません。.envファイルを確認をしてください。")
        sys.exit(1)
    
    # Botを起動をします
    bot.run(DISCORD_TOKEN)

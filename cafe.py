import os
import discord
import json
from discord.ext import tasks, commands
from discord.ui import Button, View
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9), 'JST')
TIMER_FILE = 'cafe_timers.json'

# === メインの操作パネル ===
class CafeControlView(View):
    def __init__(self, role_id, timers_dict, save_func):
        super().__init__(timeout=None)
        self.role_id = role_id
        self.timers = timers_dict
        self.save_timers = save_func

    # ボタンが押される前に自動的に呼び出されて、チャンネルと権限の検証を行います
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        allowed_channel = int(os.getenv('CAFE_CHANNEL_ID', 0))
        if interaction.channel_id != allowed_channel:
            await interaction.response.send_message("このチャンネルでは操作をすることができません。", ephemeral=True)
            return False

        user_role_ids = [r.id for r in interaction.user.roles]
        if self.role_id not in user_role_ids:
            await interaction.response.send_message("権限がありません。", ephemeral=True)
            return False
            
        return True

    # --- ボタン1: カフェタッチ完了 (前後に全角スペースを入れて幅を調整しています) ---
    @discord.ui.button(label="  カフェタッチ完了  ", style=discord.ButtonStyle.success, emoji="⏰", custom_id="cafe_btn_3h", row=0)
    async def set_3h(self, interaction: discord.Interaction, button: Button):
        next_time = datetime.now(JST) + timedelta(hours=3)
        self.timers[interaction.user.id] = next_time
        self.save_timers()
        time_str = next_time.strftime("%H:%M")

        # 押されたメッセージ自体を書き換えて、ボタンを消します
        await interaction.response.edit_message(
            content=f"✅ **カフェタッチ完了！** 次回は **{time_str}** 頃にお知らせをします。",
            view=None
        )

    # --- ボタン2: 停止 (2行目に配置をします) ---
    @discord.ui.button(label="停止", style=discord.ButtonStyle.danger, emoji="🔕", custom_id="cafe_btn_stop", row=1)
    async def stop_timer(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id in self.timers:
            del self.timers[interaction.user.id]
            self.save_timers()
            await interaction.response.edit_message(
                content="🔕 タイマーを解除しました。",
                view=None
            )
        else:
            await interaction.response.send_message("❓ タイマーはセットされていません。", ephemeral=True)

    # --- ボタン3: ヘルプ (2行目に配置をします) ---
    @discord.ui.button(label="ヘルプ", style=discord.ButtonStyle.secondary, emoji="❓", custom_id="cafe_btn_help", row=1)
    async def show_help(self, interaction: discord.Interaction, button: Button):
        help_text = (
            "**☕ カフェ管理システム ヘルプ**\n"
            "・**カフェタッチ完了**: ボタンを押すと3時間後に通知を予約します。\n"
            "・**停止**: 予約をされている通知をキャンセルします。\n"
            "・コマンド `!!cafe`: この操作パネルのランチャーボタンを呼び出します。"
        )
        # ヘルプの内容は押した本人にしか見えないメッセージとして送信をします
        await interaction.response.send_message(help_text, ephemeral=True)


# === ランチャー（パネルを開くためのスイッチ） ===
class CafeLauncherView(View):
    def __init__(self, role_id, control_view):
        super().__init__(timeout=None)
        self.role_id = role_id
        # 生成済みの操作パネルを変数として受け取ります
        self.control_view = control_view

    # ランチャーのボタンに対しても、チャンネルと権限の検証を行います
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        allowed_channel = int(os.getenv('CAFE_CHANNEL_ID', 0))
        if interaction.channel_id != allowed_channel:
            await interaction.response.send_message("このチャンネルでは操作をすることができません。", ephemeral=True)
            return False

        user_role_ids = [r.id for r in interaction.user.roles]
        if self.role_id not in user_role_ids:
            await interaction.response.send_message("権限がありません。", ephemeral=True)
            return False
            
        return True

    @discord.ui.button(label="コントロールパネルを開く (自分専用)", style=discord.ButtonStyle.secondary, emoji="🎛️", custom_id="cafe_launcher_btn")
    async def launch_panel(self, interaction: discord.Interaction, button: Button):
        # ★ここで「自分にだけ見える (ephemeral=True)」パネルを送信します
        # 新しく生成をせずに、受け取った self.control_view を使い回します
        await interaction.response.send_message(
            content="☕ **カフェ管理パネル** (このメッセージはあなたにしか見えません)",
            view=self.control_view,
            ephemeral=True
        )


class Cafe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.CAFE_ROLE_ID = int(os.getenv('CAFE_ROLE_ID'))
        self.CAFE_CHANNEL_ID = int(os.getenv('CAFE_CHANNEL_ID'))
        self.cafe_timers = {}

        self.load_timers()

        # 起動時に2種類のボタンViewを1度だけ生成をして、変数へ保存をします
        self.control_view = CafeControlView(self.CAFE_ROLE_ID, self.cafe_timers, self.save_timers)
        self.launcher_view = CafeLauncherView(self.CAFE_ROLE_ID, self.control_view)

        # 保存をしたViewをシステムへ登録をします
        self.bot.add_view(self.control_view)
        self.bot.add_view(self.launcher_view)

        self.cafe_notification_loop.start()

    def cog_unload(self):
        self.cafe_notification_loop.cancel()

    def load_timers(self):
        if os.path.exists(TIMER_FILE):
            try:
                with open(TIMER_FILE, 'r') as f:
                    data = json.load(f)
                    self.cafe_timers = {int(k): datetime.fromisoformat(v) for k, v in data.items()}
                print(f"📂 [Cafe] Loaded {len(self.cafe_timers)} timers.")
            except:
                self.cafe_timers = {}

    def save_timers(self):
        try:
            data = {str(k): v.isoformat() for k, v in self.cafe_timers.items()}
            with open(TIMER_FILE, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"⚠️ [Cafe] Save Error: {e}")

    @tasks.loop(minutes=1)
    async def cafe_notification_loop(self):
        now = datetime.now(JST)
        for user_id, schedule_time in list(self.cafe_timers.items()):
            if now >= schedule_time:
                channel = self.bot.get_channel(self.CAFE_CHANNEL_ID)
                if channel:
                    # 24時から6時までの間は、メンションを抜きにして通知を送信をします
                    if 0 <= now.hour < 6:
                        await channel.send(
                            f"先生！カフェタッチの時間です！（夜間通知）"
                        )
                    else:
                        await channel.send(
                            f"<@{user_id}> 先生！カフェタッチの時間です！"
                        )

                self.cafe_timers[user_id] = now + timedelta(hours=1)
                self.save_timers()

    # パネル設置コマンド
    @commands.command()
    async def cafe(self, ctx):
        # コマンドの実行時にもチャンネルの検証を行っています
        if ctx.channel.id != self.CAFE_CHANNEL_ID: return

        user_role_ids = [r.id for r in ctx.author.roles]
        if self.CAFE_ROLE_ID not in user_role_ids:
            await ctx.send("❌ 権限がありません。")
            return

        embed = discord.Embed(
            title="☕ シャーレ カフェタッチタイマー",
            description="下のボタンを押すと、あなた専用の操作パネルが表示されます。",
            color=0x00B0FF
        )

        # ここでも保存をした self.launcher_view を使い回します
        await ctx.send(
            embed=embed,
            view=self.launcher_view
        )

async def setup(bot):
    await bot.add_cog(Cafe(bot))

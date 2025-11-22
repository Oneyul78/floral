import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timezone, timedelta
import json

# -------------------- 🎫 토큰 입력 --------------------
TOKEN = "DSCORD_토큰"  # ★여기만 네 토큰으로 수정★

# -------------------- 💾 저장 파일 이름 --------------------
SAVE_FILE = "oneyul_data.json"  # 같은 폴더에 자동 생성/저장됨


# -------------------- 🔧 인텐트 설정 --------------------
intents = discord.Intents.default()
intents.message_content = True   # 채팅 내용 읽기
intents.members = True           # 멤버 정보 (랭킹/관리자 등)
intents.voice_states = True      # 음성채널 상태 추적

bot = commands.Bot(command_prefix="!", intents=intents)  # prefix는 안 쓰고 슬래시만 사용


# -------------------- 🚫 측정 제외 채널 / 카테고리 --------------------
# 원율이가 준 ID들: 아래 채널/카테고리들은 "점수 측정에서 제외"
EXCLUDE_CHANNEL_IDS = {
    1438217811301236867,  # #내전규칙
    1438217812442222672,  # #공식내전
    1438217812442222674,  # #내전하자
    1438217812442222675,  # #내전신청
    1438217810043207912,  # #게임모집방
    1438217802463973387,  # #사진방규칙
    1438217801042100225,  # #자유방규칙
    1438217799657848865,  # #우디승급
    1438217799657848864,  # #허브농장규칙
    1438217798978502678,  # #이름변경
    1438217798978502677,  # #통화하자
    1440746319994949815,  # #친구하자 / #꽃잎기록 (ID 같게 적혀있어서 하나만 넣음)
}

EXCLUDE_CATEGORY_IDS = {
    1438217821648715837,  # #로그
    1438217820998602838,  # #리틀포레스트
    1438217819564146710,  # #티하우스
    1438217817513267200,  # #후원
    1439802114644770929,  # #플렌테리어
    1439782553900023818,  # #글라스하우스
    1438217815541944462,  # #명령어
    1438217806964330720,  # #노래봇
    1438217804649070665,  # #공유방
    1438217796717772932,  # #홍보
    1438217794448654436,  # #후원문의
    1438217792657686742,  # #아로마
    1438217792087392417,  # #에스크
    1438217790304682085,  # #축제
    1438217787129462875,  # #생일방
    1438217788962373797,  # #신고함
    1438217785988874265,  # #단골손님
    1438217784340385843,  # #구인구직
    1438217783228891344,  # #화원문의
    1438217782167601205,  # #디자인팀
    1438217778061639682,  # #홍보팀
    1438217765893967892,  # #기획팀
    1438217762970275883,  # #뉴관팀
    1438217760944427120,  # #안내팀
    1438217749150306471,  # #보안팀
    1438217745798795399,  # #화원소모임
    1438217743894581298,  # #관리자
    1438217741877116980,  # #고관
    1438217740757499917,  # #안내
    1439897241815879793,  # #플로럴
    1438217737670230200,  # #입장
}

# 관리자 스케쥴링 알림을 보낼 채널 (원율이 지정한 ID)
ADMIN_NOTIFY_CHANNEL_ID = 1438217741877116981


# -------------------- 📊 데이터 구조 --------------------
# 채팅: {유저ID: {"by_date": {date: {"total": int, "channels": {채널ID: count}}}}}
chat_detail: dict[int, dict] = {}

# 음성: {유저ID: {"by_date": {date: {"seconds": int, "channels": {채널ID: seconds}}}}}
voice_detail: dict[int, dict] = {}

# 관리자/역할 상태
# {
#   길드ID: {
#       "admins": {유저ID: start_date},
#       "role_id": int|None,
#   }
# }
admin_state: dict[int, dict] = {}


# -------------------- 💾 저장 / 로드 --------------------
def save_data():
    """현재까지의 채팅/음성/관리자 데이터를 JSON 파일로 저장"""
    try:
        data = {
            "chat_detail": {},
            "voice_detail": {},
            "admin_state": {},
        }

        # chat_detail 직렬화
        for uid, udata in chat_detail.items():
            by_date = udata.get("by_date", {})
            ser_by_date = {}
            for d, day_data in by_date.items():
                date_str = d.isoformat()
                total = int(day_data.get("total", 0))
                ch_map = {
                    str(ch_id): int(cnt)
                    for ch_id, cnt in day_data.get("channels", {}).items()
                }
                ser_by_date[date_str] = {"total": total, "channels": ch_map}
            data["chat_detail"][str(uid)] = {"by_date": ser_by_date}

        # voice_detail 직렬화
        for uid, udata in voice_detail.items():
            by_date = udata.get("by_date", {})
            ser_by_date = {}
            for d, day_data in by_date.items():
                date_str = d.isoformat()
                seconds = int(day_data.get("seconds", 0))
                ch_map = {
                    str(ch_id): int(sec)
                    for ch_id, sec in day_data.get("channels", {}).items()
                }
                ser_by_date[date_str] = {"seconds": seconds, "channels": ch_map}
            data["voice_detail"][str(uid)] = {"by_date": ser_by_date}

        # admin_state 직렬화
        for gid, gstate in admin_state.items():
            admins = gstate.get("admins", {})
            ser_admins = {
                str(uid): d.isoformat()
                for uid, d in admins.items()
            }
            role_id = gstate.get("role_id")
            data["admin_state"][str(gid)] = {
                "admins": ser_admins,
                "role_id": role_id,
            }

        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

        print("💾 데이터 저장 완료")
    except Exception as e:
        print("⚠ save_data 에러:", repr(e))


def load_data():
    """프로그램 시작 시 JSON 파일에서 데이터 불러오기"""
    global chat_detail, voice_detail, admin_state

    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("💾 저장 파일 없음, 새로 시작합니다.")
        return
    except Exception as e:
        print("⚠ load_data 에러:", repr(e))
        return

    # chat_detail 복원
    chat_detail.clear()
    raw_chat = data.get("chat_detail", {})
    for uid_str, udata in raw_chat.items():
        try:
            uid = int(uid_str)
        except ValueError:
            continue
        by_date_raw = udata.get("by_date", {})
        by_date = {}
        for date_str, day_data in by_date_raw.items():
            try:
                d = datetime.fromisoformat(date_str).date()
            except Exception:
                continue
            total = int(day_data.get("total", 0))
            ch_raw = day_data.get("channels", {})
            ch_map = {}
            for ch_id_str, cnt in ch_raw.items():
                try:
                    ch_id = int(ch_id_str)
                    ch_map[ch_id] = int(cnt)
                except ValueError:
                    continue
            by_date[d] = {"total": total, "channels": ch_map}
        chat_detail[uid] = {"by_date": by_date}

    # voice_detail 복원
    voice_detail.clear()
    raw_voice = data.get("voice_detail", {})
    for uid_str, udata in raw_voice.items():
        try:
            uid = int(uid_str)
        except ValueError:
            continue
        by_date_raw = udata.get("by_date", {})
        by_date = {}
        for date_str, day_data in by_date_raw.items():
            try:
                d = datetime.fromisoformat(date_str).date()
            except Exception:
                continue
            seconds = int(day_data.get("seconds", 0))
            ch_raw = day_data.get("channels", {})
            ch_map = {}
            for ch_id_str, sec in ch_raw.items():
                try:
                    ch_id = int(ch_id_str)
                    ch_map[ch_id] = int(sec)
                except ValueError:
                    continue
            by_date[d] = {"seconds": seconds, "channels": ch_map}
        voice_detail[uid] = {"by_date": by_date}

    # admin_state 복원
    admin_state.clear()
    raw_admin = data.get("admin_state", {})
    for gid_str, gstate in raw_admin.items():
        try:
            gid = int(gid_str)
        except ValueError:
            continue
        admins_raw = gstate.get("admins", {})
        admins = {}
        for uid_str, date_str in admins_raw.items():
            try:
                uid = int(uid_str)
                d = datetime.fromisoformat(date_str).date()
                admins[uid] = d
            except Exception:
                continue
        role_id = gstate.get("role_id")
        if role_id is not None:
            try:
                role_id = int(role_id)
            except ValueError:
                role_id = None
        admin_state[gid] = {"admins": admins, "role_id": role_id}

    print("💾 데이터 로드 완료")


# -------------------- 🧮 유틸 함수들 --------------------
def format_duration(seconds: int) -> str:
    if seconds < 0:
        seconds = 0
    days = seconds // 86400
    seconds %= 86400
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    return f"{days}일 {hours}시간 {minutes}분 {seconds}초"


def seconds_to_points(seconds: int) -> int:
    # 1분당 2점
    if seconds <= 0:
        return 0
    minutes = (seconds + 59) // 60  # 1분 미만 올림
    return minutes * 2


def messages_to_points(count: int) -> int:
    # 채팅 1개당 2점
    if count <= 0:
        return 0
    return count * 2


def period_code_to_label(code: str) -> str:
    return {
        "total": "누적",
        "day": "일",
        "week": "주",
        "month": "월",
    }.get(code, "누적")


def get_range_for_period(code: str):
    today = datetime.now(timezone.utc).date()
    if code == "day":
        return today, today
    if code == "week":
        return today - timedelta(days=6), today  # 최근 7일
    if code == "month":
        return today - timedelta(days=29), today  # 최근 30일
    return today, today


def get_admin_state(guild_id: int):
    return admin_state.setdefault(
        guild_id,
        {"admins": {}, "role_id": None},
    )


def is_excluded_channel(ch: discord.abc.GuildChannel | None, guild_id: int) -> bool:
    """
    이 채널이 '측정 제외' 리스트에 있는지 확인
    - 특정 채널 ID
    - 특정 카테고리 ID
    """
    if ch is None:
        return False

    if ch.id in EXCLUDE_CHANNEL_IDS:
        return True

    cat = getattr(ch, "category", None)
    if cat and cat.id in EXCLUDE_CATEGORY_IDS:
        return True

    return False


# -------------------- 📊 집계 유틸: 채팅 --------------------
def aggregate_chat_for_member(user_id: int, period_code: str):
    udata = chat_detail.get(user_id)
    if not udata:
        return None

    by_date = udata.get("by_date", {})
    if not by_date:
        return None

    dates = sorted(by_date.keys())
    if not dates:
        return None

    if period_code == "total":
        start, end = dates[0], dates[-1]

        def in_range(d): return True
    else:
        start, end = get_range_for_period(period_code)

        def in_range(d): return start <= d <= end

    total = 0
    channels: dict[int, int] = {}
    has_data = False

    for d, day_data in by_date.items():
        if not in_range(d):
            continue
        day_total = day_data.get("total", 0)
        if day_total <= 0:
            continue
        has_data = True
        total += day_total
        for ch_id, cnt in day_data.get("channels", {}).items():
            channels[ch_id] = channels.get(ch_id, 0) + cnt

    if not has_data:
        return None

    return {"start": start, "end": end, "total": total, "channels": channels}


# -------------------- 📊 집계 유틸: 음성 (상시 누적) --------------------
def aggregate_voice_for_member(user_id: int, period_code: str):
    udata = voice_detail.get(user_id)
    if not udata:
        return None

    by_date = udata.get("by_date", {})
    if not by_date:
        return None

    dates = sorted(by_date.keys())
    if not dates:
        return None

    if period_code == "total":
        start, end = dates[0], dates[-1]

        def in_range(d): return True
    else:
        start, end = get_range_for_period(period_code)

        def in_range(d): return start <= d <= end

    total_seconds = 0
    channels: dict[int, int] = {}
    has_data = False

    for d, day_data in by_date.items():
        if not in_range(d):
            continue
        secs = day_data.get("seconds", 0)
        if secs <= 0:
            continue
        has_data = True
        total_seconds += secs
        for ch_id, sec in day_data.get("channels", {}).items():
            channels[ch_id] = channels.get(ch_id, 0) + sec

    if not has_data:
        return None

    return {"start": start, "end": end, "seconds": total_seconds, "channels": channels}


# -------------------- 🔁 상시 음성 기록 타이머 --------------------
@tasks.loop(seconds=60)
async def voice_auto_timer():
    """
    60초마다 길드 전체를 스캔해서
    '제외 목록'이 아닌 모든 음성 채널에 있는 사람에게 +60초씩 누적.
    """
    now = datetime.now(timezone.utc)
    today = now.date()

    for guild in bot.guilds:
        for vch in guild.voice_channels:
            if is_excluded_channel(vch, guild.id):
                continue
            if not vch.members:
                continue

            for member in vch.members:
                if member.bot:
                    continue

                uid = member.id
                udata = voice_detail.setdefault(uid, {"by_date": {}})
                by_date = udata["by_date"]
                day_data = by_date.setdefault(today, {"seconds": 0, "channels": {}})

                day_data["seconds"] += 60
                day_data["channels"][vch.id] = day_data["channels"].get(vch.id, 0) + 60


# -------------------- 🔁 관리자 스케줄러 (매일, 30일 단위로 알림) --------------------
@tasks.loop(hours=24)
async def admin_scheduler():
    """매일 1번 돌면서 30일 단위로 관리자 알림 보내기"""
    today = datetime.now(timezone.utc).date()

    for guild in bot.guilds:
        # 고정된 알림 채널 ID 사용
        channel = guild.get_channel(ADMIN_NOTIFY_CHANNEL_ID)
        if not channel or not hasattr(channel, "send"):
            continue

        state = admin_state.get(guild.id)
        if not state:
            continue

        role_id = state.get("role_id")
        role = guild.get_role(role_id) if role_id else None

        admins = state.get("admins", {})
        for user_id, start_date in admins.items():
            member = guild.get_member(user_id)
            if not member:
                continue

            days = (today - start_date).days + 1
            if days <= 0:
                continue

            if days % 30 == 0:  # 30일마다
                lines = []
                if role:
                    lines.append(role.mention)
                lines.append("**관리자 스케쥴링**")
                lines.append(f"{member.mention} 관리자 {days}일째 입니다")
                await channel.send("\n".join(lines))


# -------------------- 🔁 자동 저장 타이머 --------------------
@tasks.loop(seconds=60)
async def autosave_task():
    """1분마다 현재 데이터 자동 저장"""
    save_data()


# -------------------- 🟢 on_ready --------------------
@bot.event
async def on_ready():
    print(f"✅ 로그인 완료: {bot.user}")
    try:
        synced = await bot.tree.sync()  # 슬래시 명령어 동기화
        print(f"🔧 슬래시 명령어 {len(synced)}개 동기화 완료")
    except Exception as e:
        print("⚠ 슬래시 명령어 동기화 실패:", repr(e))

    if not voice_auto_timer.is_running():
        voice_auto_timer.start()
        print("▶ voice_auto_timer started")

    if not admin_scheduler.is_running():
        admin_scheduler.start()
        print("▶ admin_scheduler started")

    if not autosave_task.is_running():
        autosave_task.start()
        print("▶ autosave_task started")


# -------------------- 💬 채팅 수집 --------------------
@bot.event
async def on_message(message: discord.Message):
    # 봇 / DM / 시스템 등은 무시
    if message.author.bot or not message.guild:
        return

    # 제외 대상 채널/카테고리면 무시
    if is_excluded_channel(message.channel, message.guild.id):
        return

    user_id = message.author.id
    channel_id = message.channel.id
    msg_date = message.created_at.astimezone(timezone.utc).date()

    udata = chat_detail.setdefault(user_id, {"by_date": {}})
    by_date = udata["by_date"]
    day_data = by_date.setdefault(msg_date, {"total": 0, "channels": {}})

    day_data["total"] += 1
    day_data["channels"][channel_id] = day_data["channels"].get(channel_id, 0) + 1

    # 슬래시만 쓰므로 process_commands는 안 부름


# -------------------- 📌 임베드: 채팅 --------------------
def build_chat_embed(guild: discord.Guild, member: discord.Member, period_code: str) -> discord.Embed:
    label = period_code_to_label(period_code)
    agg = aggregate_chat_for_member(member.id, period_code)

    if not agg:
        if period_code == "total":
            today = datetime.now(timezone.utc).date()
            start, end = today, today
        else:
            start, end = get_range_for_period(period_code)
        desc = (
            f"{member.mention}의 {label}({start} ~ {end}) 기록입니다.\n\n"
            "채팅 기록이 아직 없습니다.\n"
            "반영까지 최대 1분이 소요될 수 있습니다."
        )
        return discord.Embed(title="📊 채팅 기록 확인", description=desc, color=discord.Color.green())

    start = agg["start"]
    end = agg["end"]
    total = agg["total"]
    channels = agg["channels"]
    total_points = messages_to_points(total)

    category_info: dict[str, dict] = {}
    for ch_id, cnt in channels.items():
        channel = guild.get_channel(ch_id)
        if isinstance(channel, discord.TextChannel):
            cat_name = channel.category.name if channel.category else "카테고리 없음"
            ch_name = f"#{channel.name}"
        else:
            cat_name = "알 수 없는 카테고리"
            ch_name = f"알 수 없는 채널({ch_id})"
        cat = category_info.setdefault(cat_name, {"messages": 0, "channels": []})
        cat["messages"] += cnt
        cat["channels"].append((ch_name, cnt))

    lines: list[str] = []
    lines.append(f"{member.mention}의 {label}({start} ~ {end}) 기록입니다.\n")

    for cat_name, info in category_info.items():
        cat_msgs = info["messages"]
        cat_points = messages_to_points(cat_msgs)
        lines.append(f"**{cat_name}**")
        for ch_name, cnt in sorted(info["channels"], key=lambda x: x[1], reverse=True):
            ch_points = messages_to_points(cnt)
            lines.append(f"- {ch_name}: {ch_points}점 ({cnt}개)")
        lines.append(f"{cat_name} 종합채팅: {cat_msgs}개 ({cat_points}점)\n")

    lines.append("───────── ౨ৎ ─────────")
    lines.append(f"종합: {total}개 ({total_points}점)\n")
    lines.append("반영까지 최대 1분이 소요될 수 있습니다.")

    return discord.Embed(title="📊 채팅 기록 확인", description="\n".join(lines), color=discord.Color.green())


# -------------------- 📌 임베드: 음성 --------------------
def build_voice_embed(guild: discord.Guild, member: discord.Member, period_code: str) -> discord.Embed:
    label = period_code_to_label(period_code)
    agg = aggregate_voice_for_member(member.id, period_code)

    if not agg:
        if period_code == "total":
            today = datetime.now(timezone.utc).date()
            start, end = today, today
        else:
            start, end = get_range_for_period(period_code)
        desc = (
            f"{member.mention}의 {label}({start} ~ {end}) 기록입니다.\n\n"
            "음성 채널 기록이 아직 없습니다.\n"
            "반영까지 최대 1분이 소요될 수 있습니다."
        )
        return discord.Embed(title="🎧 음성 기록 확인", description=desc, color=discord.Color.blue())

    start = agg["start"]
    end = agg["end"]
    total_seconds = agg["seconds"]
    channels = agg["channels"]
    total_points = seconds_to_points(total_seconds)

    category_info: dict[str, dict] = {}
    for ch_id, sec in channels.items():
        channel = guild.get_channel(ch_id)
        if isinstance(channel, discord.VoiceChannel):
            cat_name = channel.category.name if channel.category else "카테고리 없음"
            ch_name = channel.name
        else:
            cat_name = "알 수 없는 카테고리"
            ch_name = f"알 수 없는 채널({ch_id})"
        cat = category_info.setdefault(cat_name, {"seconds": 0, "channels": []})
        cat["seconds"] += sec
        cat["channels"].append((ch_name, sec))

    lines: list[str] = []
    lines.append(f"{member.mention}의 {label}({start} ~ {end}) 기록입니다.\n")

    for cat_name, info in category_info.items():
        cat_secs = info["seconds"]
        cat_points = seconds_to_points(cat_secs)
        lines.append(f"**{cat_name}**")
        for ch_name, sec in sorted(info["channels"], key=lambda x: x[1], reverse=True):
            ch_points = seconds_to_points(sec)
            lines.append(f"- {ch_name}: {format_duration(sec)} ({ch_points}점)")
        lines.append(f"{cat_name} 종합시간: {format_duration(cat_secs)} ({cat_points}점)\n")

    lines.append("───────── ౨ৎ ─────────")
    lines.append(f"종합: {format_duration(total_seconds)} ({total_points}점)\n")
    lines.append("반영까지 최대 1분이 소요될 수 있습니다.")

    return discord.Embed(title="🎧 음성 기록 확인", description="\n".join(lines), color=discord.Color.blue())


# -------------------- 📈 랭킹 임베드 (채팅/음성/합산) --------------------
def build_chat_rank_embed(guild: discord.Guild, period_code: str, role: discord.Role | None) -> discord.Embed:
    label = period_code_to_label(period_code)
    rank_list = []
    global_start, global_end = None, None

    for m in guild.members:
        if m.bot:
            continue
        if role and role not in m.roles:
            continue

        agg = aggregate_chat_for_member(m.id, period_code)
        if not agg:
            continue

        total = agg["total"]
        points = messages_to_points(total)
        if points <= 0:
            continue

        rank_list.append((m, total, points))
        s, e = agg["start"], agg["end"]
        if global_start is None or s < global_start:
            global_start = s
        if global_end is None or e > global_end:
            global_end = e

    if not rank_list:
        if period_code == "total":
            today = datetime.now(timezone.utc).date()
            start, end = today, today
        else:
            start, end = get_range_for_period(period_code)
        desc = f"**채팅 랭킹**\n기간: {label}({start} ~ {end})\n대상: {role.mention if role else '서버 전체'}\n\n기록이 없습니다."
        return discord.Embed(title="📊 채팅 랭킹", description=desc, color=discord.Color.gold())

    rank_list.sort(key=lambda x: x[2], reverse=True)
    if global_start is None or global_end is None:
        global_start, global_end = get_range_for_period(period_code)

    lines = []
    lines.append(f"기간: {label}({global_start} ~ {global_end})")
    lines.append(f"대상: {role.mention if role else '서버 전체'}\n")
    for idx, (m, total, points) in enumerate(rank_list[:10], start=1):
        lines.append(f"{idx}. {m.display_name} - {points}점 ({total}개)")
    lines.append("\n반영까지 최대 1분이 소요될 수 있습니다.")

    return discord.Embed(title="📊 채팅 랭킹", description="\n".join(lines), color=discord.Color.gold())


def build_voice_rank_embed(guild: discord.Guild, period_code: str, role: discord.Role | None) -> discord.Embed:
    label = period_code_to_label(period_code)
    rank_list = []
    global_start, global_end = None, None

    for m in guild.members:
        if m.bot:
            continue
        if role and role not in m.roles:
            continue

        agg = aggregate_voice_for_member(m.id, period_code)
        if not agg:
            continue

        secs = agg["seconds"]
        points = seconds_to_points(secs)
        if points <= 0:
            continue

        rank_list.append((m, secs, points))
        s, e = agg["start"], agg["end"]
        if global_start is None or s < global_start:
            global_start = s
        if global_end is None or e > global_end:
            global_end = e

    if not rank_list:
        if period_code == "total":
            today = datetime.now(timezone.utc).date()
            start, end = today, today
        else:
            start, end = get_range_for_period(period_code)
        desc = f"**음성 랭킹**\n기간: {label}({start} ~ {end})\n대상: {role.mention if role else '서버 전체'}\n\n기록이 없습니다."
        return discord.Embed(title="🎧 음성 랭킹", description=desc, color=discord.Color.gold())

    rank_list.sort(key=lambda x: x[2], reverse=True)
    if global_start is None or global_end is None:
        global_start, global_end = get_range_for_period(period_code)

    lines = []
    lines.append(f"기간: {label}({global_start} ~ {global_end})")
    lines.append(f"대상: {role.mention if role else '서버 전체'}\n")
    for idx, (m, secs, points) in enumerate(rank_list[:10], start=1):
        lines.append(f"{idx}. {m.display_name} - {points}점 ({format_duration(secs)})")
    lines.append("\n반영까지 최대 1분이 소요될 수 있습니다.")

    return discord.Embed(title="🎧 음성 랭킹", description="\n".join(lines), color=discord.Color.gold())


def build_total_rank_embed(guild: discord.Guild, period_code: str, role: discord.Role | None) -> discord.Embed:
    """채팅+음성 총합 랭킹 (/rank_all)"""
    label = period_code_to_label(period_code)
    rank_list = []
    global_start, global_end = None, None

    for m in guild.members:
        if m.bot:
            continue
        if role and role not in m.roles:
            continue

        agg_chat = aggregate_chat_for_member(m.id, period_code)
        agg_voice = aggregate_voice_for_member(m.id, period_code)
        if not agg_chat and not agg_voice:
            continue

        chat_cnt = agg_chat["total"] if agg_chat else 0
        chat_pts = messages_to_points(chat_cnt)
        voice_secs = agg_voice["seconds"] if agg_voice else 0
        voice_pts = seconds_to_points(voice_secs)
        total_pts = chat_pts + voice_pts
        if total_pts <= 0:
            continue

        rank_list.append((m, total_pts, chat_cnt, chat_pts, voice_secs, voice_pts))

        for agg in (agg_chat, agg_voice):
            if not agg:
                continue
            s, e = agg["start"], agg["end"]
            if global_start is None or s < global_start:
                global_start = s
            if global_end is None or e > global_end:
                global_end = e

    if not rank_list:
        if period_code == "total":
            today = datetime.now(timezone.utc).date()
            start, end = today, today
        else:
            start, end = get_range_for_period(period_code)
        desc = f"**종합 랭킹**\n기간: {label}({start} ~ {end})\n대상: {role.mention if role else '서버 전체'}\n\n기록이 없습니다."
        return discord.Embed(title="📊 종합 랭킹", description=desc, color=discord.Color.purple())

    rank_list.sort(key=lambda x: x[1], reverse=True)
    if global_start is None or global_end is None:
        global_start, global_end = get_range_for_period(period_code)

    lines = []
    lines.append(f"기간: {label}({global_start} ~ {global_end})")
    lines.append(f"대상: {role.mention if role else '서버 전체'}\n")
    for idx, (m, total_pts, chat_cnt, chat_pts, voice_secs, voice_pts) in enumerate(rank_list[:10], start=1):
        lines.append(
            f"{idx}. {m.display_name} - 총 {total_pts}점 "
            f"(채팅 {chat_pts}점/{chat_cnt}개, 음성 {voice_pts}점/{format_duration(voice_secs)})"
        )

    lines.append("\n반영까지 최대 1분이 소요될 수 있습니다.")

    return discord.Embed(title="📊 종합 랭킹", description="\n".join(lines), color=discord.Color.purple())


# -------------------- ⌨ 슬래시용 기간 선택 --------------------
period_choices = [
    app_commands.Choice(name="누적", value="total"),
    app_commands.Choice(name="일 (오늘)", value="day"),
    app_commands.Choice(name="주 (최근 7일)", value="week"),
    app_commands.Choice(name="월 (최근 30일)", value="month"),
]


# -------------------- ⌨ 슬래시: 기본 테스트 --------------------
@bot.tree.command(name="ping", description="봇 상태 확인")
async def ping_slash(interaction: discord.Interaction):
    await interaction.response.send_message("pong!")


# -------------------- ⌨ 슬래시: /voice_log (음성 기록 확인) --------------------
@bot.tree.command(name="voice_log", description="음성 기록 확인")
@app_commands.choices(period=period_choices)
@app_commands.describe(member="기록을 볼 유저")
async def voice_log_slash(
    interaction: discord.Interaction,
    period: app_commands.Choice[str],
    member: discord.Member | None = None,
):
    if interaction.guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능해요.")
        return

    member = member or interaction.user
    embed = build_voice_embed(interaction.guild, member, period.value)
    await interaction.response.send_message(embed=embed)


# -------------------- ⌨ 슬래시: /chat_log (채팅 기록 확인) --------------------
@bot.tree.command(name="chat_log", description="채팅 기록 확인")
@app_commands.choices(period=period_choices)
@app_commands.describe(member="기록을 볼 유저")
async def chat_log_slash(
    interaction: discord.Interaction,
    period: app_commands.Choice[str],
    member: discord.Member | None = None,
):
    if interaction.guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능해요.")
        return

    member = member or interaction.user
    embed = build_chat_embed(interaction.guild, member, period.value)
    await interaction.response.send_message(embed=embed)


# -------------------- ⌨ 슬래시: /voice_rank (음성 랭킹) --------------------
@bot.tree.command(name="voice_rank", description="음성 랭킹 보기")
@app_commands.choices(period=period_choices)
@app_commands.describe(role="이 역할을 가진 사람들만 랭킹 보기 (선택)")
async def voice_rank_slash(
    interaction: discord.Interaction,
    period: app_commands.Choice[str],
    role: discord.Role | None = None,
):
    if interaction.guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능해요.")
        return

    embed = build_voice_rank_embed(interaction.guild, period.value, role)
    await interaction.response.send_message(embed=embed)


# -------------------- ⌨ 슬래시: /chat_rank (채팅 랭킹) --------------------
@bot.tree.command(name="chat_rank", description="채팅 랭킹 보기")
@app_commands.choices(period=period_choices)
@app_commands.describe(role="이 역할을 가진 사람들만 랭킹 보기 (선택)")
async def chat_rank_slash(
    interaction: discord.Interaction,
    period: app_commands.Choice[str],
    role: discord.Role | None = None,
):
    if interaction.guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능해요.")
        return

    embed = build_chat_rank_embed(interaction.guild, period.value, role)
    await interaction.response.send_message(embed=embed)


# -------------------- ⌨ 슬래시: /rank_all (채팅+보이스 합산 랭킹) --------------------
@bot.tree.command(name="rank_all", description="채팅+음성 종합 랭킹 보기")
@app_commands.choices(period=period_choices)
@app_commands.describe(role="이 역할을 가진 사람들만 랭킹 보기 (선택)")
async def rank_all_slash(
    interaction: discord.Interaction,
    period: app_commands.Choice[str],
    role: discord.Role | None = None,
):
    if interaction.guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능해요.")
        return

    embed = build_total_rank_embed(interaction.guild, period.value, role)
    await interaction.response.send_message(embed=embed)


# -------------------- ⌨ 슬래시: 관리자 관련 --------------------
@bot.tree.command(name="admin_set", description="관리자 설정 (시작 날짜 직접 지정)")
@app_commands.describe(
    user="관리자로 등록할 유저",
    start_date="시작 날짜 (예: 2025-11-22, 비우면 오늘 날짜)",
)
async def admin_set_slash(
    interaction: discord.Interaction,
    user: discord.Member,
    start_date: str | None = None,
):
    if interaction.guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능해요.")
        return

    if start_date is None or start_date.strip() == "":
        dt = datetime.now(timezone.utc).date()
    else:
        try:
            dt = datetime.strptime(start_date.strip(), "%Y-%m-%d").date()
        except ValueError:
            await interaction.response.send_message(
                "날짜 형식은 `YYYY-MM-DD` 예: `2025-11-22` 처럼 입력해줘.",
            )
            return

    state = get_admin_state(interaction.guild.id)
    admins = state["admins"]
    admins[user.id] = dt

    await interaction.response.send_message(
        f"{user.mention} 님을 {dt}부터 관리자 스케쥴링 대상으로 등록했습니다. "
        f"(현재 등록 관리자 수: {len(admins)}명)",
    )


@bot.tree.command(name="admin_list", description="관리자 확인")
async def admin_list_slash(interaction: discord.Interaction):
    if interaction.guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능해요.")
        return

    state = get_admin_state(interaction.guild.id)
    admins = state["admins"]

    if not admins:
        await interaction.response.send_message("등록된 관리자가 없습니다.")
        return

    today = datetime.now(timezone.utc).date()
    lines = ["**관리자 확인**"]

    for user_id, start_date in admins.items():
        days = (today - start_date).days + 1
        member = interaction.guild.get_member(user_id)
        mention = member.mention if member else f"<@{user_id}>"
        lines.append(f"{mention} - {days}일 (시작일: {start_date})")

    embed = discord.Embed(
        title="관리자 확인",
        description="\n".join(lines),
        color=discord.Color.orange(),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="admin_remove", description="관리자 삭제")
@app_commands.describe(user="관리자에서 제거할 유저")
async def admin_remove_slash(
    interaction: discord.Interaction,
    user: discord.Member,
):
    if interaction.guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능해요.")
        return

    state = get_admin_state(interaction.guild.id)
    admins = state["admins"]

    if user.id in admins:
        admins.pop(user.id)
        await interaction.response.send_message(
            f"{user.mention} 님을 관리자 목록에서 제거했습니다.",
        )
    else:
        await interaction.response.send_message(
            "해당 유저는 관리자 목록에 없습니다.",
        )


@bot.tree.command(name="admin_role", description="관리자 알림에 멘션할 역할 설정")
@app_commands.describe(role="알림에 함께 멘션할 역할")
async def admin_role_slash(
    interaction: discord.Interaction,
    role: discord.Role,
):
    if interaction.guild is None:
        await interaction.response.send_message("서버 안에서만 사용 가능해요.")
        return

    state = get_admin_state(interaction.guild.id)
    state["role_id"] = role.id

    await interaction.response.send_message(
        f"관리자 알림에 {role.mention} 역할을 멘션하도록 설정했습니다.",
    )


# -------------------- 🚀 실행 --------------------
if __name__ == "__main__":
    # 시작할 때 이전 데이터 로드
    load_data()
    # 봇 실행

    bot.run(TOKEN)

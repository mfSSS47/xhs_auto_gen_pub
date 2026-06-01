from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Optional

from models.database import SessionLocal, init_db
from services.account_service import account_service
from services.content_service import content_service
from services.pipeline import PipelineResult, content_pipeline
from utils.logger import setup_logger


def _safe_print(text: str) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print(text)


def _display_result(result: PipelineResult) -> None:
    if result.success:
        _safe_print("\n" + "=" * 60)
        _safe_print("  PIPELINE COMPLETED SUCCESSFULLY")
        _safe_print("=" * 60)
    else:
        _safe_print("\n" + "=" * 60)
        _safe_print(f"  PIPELINE FAILED at stage: {result.stage}")
        _safe_print("=" * 60)
        if result.error:
            _safe_print(f"  Error: {result.error}")
        return

    _safe_print(f"  Direction ID : {result.direction_id}")
    if result.post_id:
        _safe_print(f"  Post ID      : {result.post_id}")
    if result.post_title:
        _safe_print(f"\n  --- TITLE ---")
        _safe_print(f"  {result.post_title}")
    if result.post_body:
        _safe_print(f"\n  --- BODY ({len(result.post_body)} chars) ---")
        _safe_print(result.post_body)
    if result.hashtags:
        _safe_print(f"\n  --- HASHTAGS ---")
        _safe_print(f"  {'  '.join('#' + t for t in result.hashtags)}")
    if result.review_score is not None:
        _safe_print(f"\n  Review Score  : {result.review_score:.1f}/10")
    if result.review_issues:
        _safe_print(f"  Review Issues : {', '.join(result.review_issues)}")
    if result.platform_post_id:
        _safe_print(f"  Platform ID   : {result.platform_post_id}")
    _safe_print("\n" + "=" * 60)


def cmd_generate(args: argparse.Namespace) -> None:
    init_db()

    kw_list = [k.strip() for k in args.keywords.split(",")] if args.keywords else None

    print(f"\n  Topic   : {args.topic}")
    print(f"  Tone    : {args.tone}")
    print(f"  Audience: {args.audience or 'default'}")
    print(f"  Keywords: {kw_list or 'none'}")
    print(f"  Publish : {args.publish}")
    print()

    print("Running pipeline...")
    result = asyncio.run(
        content_pipeline.run_full(
            topic=args.topic,
            tone=args.tone,
            target_audience=args.audience,
            keywords=kw_list,
            category=args.category or "",
            max_length=args.max_length,
            image_count=args.images,
            extra_context=args.extra or "",
            auto_publish=args.publish,
            account_id=args.account,
        )
    )
    _display_result(result)


def cmd_generate_only(args: argparse.Namespace) -> None:
    init_db()

    kw_list = [k.strip() for k in args.keywords.split(",")] if args.keywords else None

    print(f"\n  Topic   : {args.topic}")
    print(f"  Tone    : {args.tone}")
    print()

    print("Generating content...")
    result = asyncio.run(
        content_pipeline.run_generate_only(
            topic=args.topic,
            tone=args.tone,
            target_audience=args.audience,
            keywords=kw_list,
            max_length=args.max_length,
            extra_context=args.extra or "",
        )
    )
    _display_result(result)


def cmd_account_add(args: argparse.Namespace) -> None:
    init_db()
    db = SessionLocal()
    try:
        acc = account_service.create_account(
            db=db, credential=args.credential, platform=args.platform, nickname=args.nickname,
        )
        print(f"Account created: {acc.id} ({acc.nickname})")
    finally:
        db.close()


def cmd_account_list(args: argparse.Namespace) -> None:
    init_db()
    db = SessionLocal()
    try:
        accounts = account_service.list_accounts(db=db, platform=args.platform)
        if not accounts:
            print("No accounts found.")
            return
        print(f"\n{'ID':<14} {'Platform':<10} {'Nickname':<15} {'Status':<10}")
        print("-" * 50)
        for a in accounts:
            print(f"{a.id:<14} {a.platform:<10} {a.nickname or '-':<15} {a.status:<10}")
    finally:
        db.close()


def cmd_account_verify(args: argparse.Namespace) -> None:
    init_db()
    db = SessionLocal()
    try:
        valid = account_service.verify_account(db=db, account_id=args.account_id)
        if valid:
            print(f"Account {args.account_id} credential is VALID.")
        else:
            print(f"Account {args.account_id} credential is INVALID.")
    finally:
        db.close()


def cmd_directions(args: argparse.Namespace) -> None:
    init_db()
    db = SessionLocal()
    try:
        items = content_service.list_directions(db=db)
        if not items:
            print("No content directions found.")
            return
        print(f"\n{'ID':<14} {'Topic':<40} {'Tone':<12} {'Status':<12} {'Created':<20}")
        print("-" * 100)
        for d in items:
            created = d.created_at.strftime("%Y-%m-%d %H:%M") if d.created_at else "-"
            print(f"{d.id:<14} {d.topic[:38]:<40} {d.tone or '-':<12} {d.status:<12} {created:<20}")
    finally:
        db.close()


def cmd_cleanup(args: argparse.Namespace) -> None:
    """清理所有残留文件，确保干净状态。"""
    import subprocess
    from adapters.ai.claude_adapter import cleanup_claude_files

    # 1. Clean claude files
    cleanup_claude_files()

    # 2. Kill any lingering pipeline processes
    killed = 0
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True,
        )
        for line in result.stdout.strip().split("\n"):
            if "main.py" in line:
                pid = line.split(",")[1].strip('"')
                try:
                    subprocess.run(["taskkill", "/F", "/PID", pid],
                                   capture_output=True)
                    killed += 1
                except Exception:
                    pass
    except Exception:
        pass

    print(f"  Cleanup: claude files cleared, {killed} zombie process(es) killed")
    print("  Ready for next publish.")


def main() -> None:
    setup_logger()

    parser = argparse.ArgumentParser(
        description="小红书自动化内容生成与发布系统",
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    gen_parser = subparsers.add_parser("generate", help="一键生成并（可选）发布小红书帖子")
    gen_parser.add_argument("-t", "--topic", required=True, help="内容主题/方向")
    gen_parser.add_argument("--tone", default="casual", choices=["casual", "professional", "storytelling", "tutorial"], help="内容风格")
    gen_parser.add_argument("-a", "--audience", default="", help="目标受众")
    gen_parser.add_argument("-k", "--keywords", default=None, help="关键词，逗号分隔")
    gen_parser.add_argument("-c", "--category", default="", help="内容分类")
    gen_parser.add_argument("--max-length", type=int, default=1000, help="最大字数")
    gen_parser.add_argument("--images", type=int, default=1, help="图片数量")
    gen_parser.add_argument("-e", "--extra", default="", help="额外上下文")
    gen_parser.add_argument("--publish", action="store_true", default=False, help="是否自动发布")
    gen_parser.add_argument("--account", default=None, help="发布账号ID")

    gen_only = subparsers.add_parser("gen-only", help="仅生成内容（不审核、不发布）")
    gen_only.add_argument("-t", "--topic", required=True, help="内容主题/方向")
    gen_only.add_argument("--tone", default="casual", choices=["casual", "professional", "storytelling", "tutorial"], help="内容风格")
    gen_only.add_argument("-a", "--audience", default="", help="目标受众")
    gen_only.add_argument("-k", "--keywords", default=None, help="关键词，逗号分隔")
    gen_only.add_argument("--max-length", type=int, default=1000, help="最大字数")
    gen_only.add_argument("-e", "--extra", default="", help="额外上下文")

    acc_add = subparsers.add_parser("account-add", help="添加平台账号凭证")
    acc_add.add_argument("--credential", required=True, help="平台Cookie/Token")
    acc_add.add_argument("-n", "--nickname", default="", help="账号昵称")
    acc_add.add_argument("--platform", default="xhs", help="平台标识")

    subparsers.add_parser("account-list", help="列出已添加的账号").add_argument("--platform", default="xhs")

    acc_verify = subparsers.add_parser("account-verify", help="验证账号凭证")
    acc_verify.add_argument("--account-id", required=True, help="账号ID")

    subparsers.add_parser("directions", help="查看内容方向列表")

    subparsers.add_parser("cleanup", help="清理残留文件和僵尸进程")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    commands = {
        "generate": cmd_generate,
        "gen-only": cmd_generate_only,
        "account-add": cmd_account_add,
        "account-list": cmd_account_list,
        "account-verify": cmd_account_verify,
        "directions": cmd_directions,
        "cleanup": cmd_cleanup,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()

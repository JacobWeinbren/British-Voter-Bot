"""Command line entry point: python -m voterbot <command>.

  build     queue every eligible BES respondent (weighted order) in outputs/profiles.jsonl.gz
  render    render one or more profiles to PNG (for checking the design)
  preview   fifty varied cards in posting form (1600x2000 lossless WebP) plus post and alt text
  post      render the next profile in the queue, post it to Bluesky, advance the queue
  alt       print the post text and alt text for a queued card
  brand     regenerate the Bluesky banner, avatar and pinned intro poster (with alt text files) in outputs/brand
  stats     summarise the queue (nations, parties, issues)
  audit     rewrite docs/unused-questions.md: which wave-20+ questions are used and why the rest are not
"""

from __future__ import annotations

import argparse
import collections
import sys

from . import config


def cmd_build(args) -> None:
    from .data import load_panel
    from .sample import build_profiles

    panel = load_panel()
    build_profiles(panel, count=args.count, seed=args.seed)


def cmd_render(args) -> None:
    from .render import render_png
    from .sample import load_profiles

    profiles = load_profiles()
    indices = range(args.start, min(args.start + args.count, len(profiles)))
    for i in indices:
        out = render_png(profiles[i], config.PREVIEW_DIR / f"card_{i:04d}.png", keep_html=args.html)
        print(f"rendered {out}")


def cmd_preview(args) -> None:
    """Fifty varied cards in their posting form (1600x2000 lossless WebP) plus the post and alt text for each."""
    from .render import render_card
    from .sample import load_profiles

    profiles = load_profiles()
    plain = lambda span: span["template"].format(**span["bold"]) if span else ""
    picks: list[int] = []

    def add(test, count=1):
        for i, p in enumerate(profiles):
            if count == 0:
                break
            if i not in picks and test(p):
                picks.append(i)
                count -= 1

    # a spread of what the feed will show, then the head of the queue in order
    add(lambda p: p["country"] == 2, 6)
    add(lambda p: p["country"] == 3, 4)
    add(lambda p: "don't know who" in p["band_text"], 2)
    add(lambda p: "wouldn't either" in p["band_text"], 2)
    add(lambda p: "smaller party" in p["band_text"])
    add(lambda p: p.get("econ_pct") is None)
    add(lambda p: not p.get("top_issue"))
    add(lambda p: "student" in plain(p["life"]))
    add(lambda p: "out of work" in plain(p["life"]))
    add(lambda p: "retired" in plain(p["life"]))
    add(lambda p: "politics from" in plain(p["media"]))
    for party in ("Labour", "Conservative", "Reform UK", "Lib Dem", "Green", "SNP", "Plaid Cymru"):
        add(lambda p, party=party: p["intention_party"] == party)
    add(lambda p: True, args.count - len(picks))
    picks = picks[: args.count]

    config.PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    for old in list(config.PREVIEW_DIR.glob("*.png")) + list(config.PREVIEW_DIR.glob("*.webp")) + list(config.PREVIEW_DIR.glob("*.md")):
        old.unlink()
    with open(config.PREVIEW_DIR / "alt_texts.md", "w", encoding="utf-8") as fh:
        fh.write("# Post text and alt text for the preview cards\n\n")
        for n, i in enumerate(picks):
            p = profiles[i]
            png, webp = render_card(p, config.PREVIEW_DIR / f"card_{n:02d}.png")
            png.unlink()  # the WebP is the posting form; the PNG was only the intermediate
            fh.write(f"## {webp.name}\n\n**Post text**\n\n{p['post_text']}\n\n**Alt text** ({len(p['alt_text'])} characters)\n\n{p['alt_text']}\n\n")
    print(f"rendered {len(picks)} cards as lossless WebP and alt_texts.md in {config.PREVIEW_DIR}")


def cmd_post(args) -> None:
    from .bluesky import post_card
    from .render import render_card
    from .sample import load_profiles, read_position, write_position

    profiles = load_profiles()
    position = read_position()
    if position >= len(profiles):
        print("Queue exhausted - run `build` to generate more profiles.")
        sys.exit(1)
    profile = profiles[position]
    png, webp = render_card(profile, config.CARDS_DIR / f"card_{position:04d}.png")
    if args.dry_run:
        print(f"[dry run] would post profile {position}:\n{profile['post_text']}\nimage: {webp} (fallback {png})\n"
              f"alt text ({len(profile['alt_text'])} characters): {profile['alt_text']}")
        return
    uri = post_card(profile["post_text"], webp, profile["alt_text"], fallback_path=png)
    write_position(position + 1)
    print(f"Posted profile {position} ({profile['constituency']}) with {len(profile['alt_text'])}-character alt text: {uri}")


def cmd_alt(args) -> None:
    """Show the post text and the alt text that would accompany a card."""
    from .sample import load_profiles

    profiles = load_profiles()
    profile = profiles[args.index]
    print("POST TEXT\n" + profile["post_text"])
    print(f"\nALT TEXT ({len(profile['alt_text'])} characters)\n" + profile["alt_text"])


def cmd_brand(args) -> None:
    from .brand import make_brand_assets, make_intro_poster

    banner, avatar = make_brand_assets()
    poster = make_intro_poster()
    print(f"wrote {banner}, {avatar} and {poster}")


def cmd_stats(args) -> None:
    from .sample import load_profiles

    profiles = load_profiles()
    print(f"{len(profiles)} profiles - about {len(profiles) / (config.POSTS_PER_DAY * 365):.1f} years at {config.POSTS_PER_DAY} a day")
    for key in ("nation", "intention_party", "top_issue"):
        counts = collections.Counter(p.get(key) or "none" for p in profiles)
        print(f"\n{key}:")
        for name, n in counts.most_common(12):
            print(f"  {name:<32} {n:5d}  {n / len(profiles):5.1%}")
    topics = collections.Counter(b["template"][:40] for p in profiles for b in p["bubbles"][1:])
    print(f"\n{len(topics)} distinct opinion sentences in use; most common:")
    for text, n in topics.most_common(8):
        print(f"  {n:4d}  {text}...")


def cmd_audit(args) -> None:
    from .audit import write_audit

    print("wrote", write_audit())


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="voterbot", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="queue every eligible respondent (or --count of them) in weighted order")
    build.add_argument("--count", type=int, default=config.PROFILE_COUNT, help="stop after this many cards (default: no cap)")
    build.add_argument("--seed", type=int, default=config.RANDOM_SEED)
    build.set_defaults(func=cmd_build)

    render = sub.add_parser("render", help="render profiles to PNG previews")
    render.add_argument("--start", type=int, default=0)
    render.add_argument("--count", type=int, default=1)
    render.add_argument("--html", action="store_true", help="also keep the HTML next to the PNG")
    render.set_defaults(func=cmd_render)

    post = sub.add_parser("post", help="post the next card to Bluesky")
    post.add_argument("--dry-run", action="store_true", help="render but do not post or advance the queue")
    post.set_defaults(func=cmd_post)

    preview = sub.add_parser("preview", help="render varied cards in posting form (lossless WebP) with their alt text")
    preview.add_argument("--count", type=int, default=50)
    preview.set_defaults(func=cmd_preview)

    alt = sub.add_parser("alt", help="print the post text and alt text for a queued card")
    alt.add_argument("--index", type=int, default=0)
    alt.set_defaults(func=cmd_alt)

    sub.add_parser("brand", help="regenerate banner, avatar and intro poster with their alt text").set_defaults(func=cmd_brand)
    sub.add_parser("stats", help="summarise the profile queue").set_defaults(func=cmd_stats)
    sub.add_parser("audit", help="rewrite docs/unused-questions.md").set_defaults(func=cmd_audit)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

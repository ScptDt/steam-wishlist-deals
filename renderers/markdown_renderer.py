from __future__ import annotations

from datetime import date

from .common import markdown_escape


STORE_URL = "https://store.steampowered.com/app/{appid}/"

MESES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}


def _md_esc(text: str) -> str:
    return markdown_escape(text)


def _link(name: str, appid: str) -> str:
    return f"[{_md_esc(name)}]({STORE_URL.format(appid=appid)})"


def _yaml_quote(text: str) -> str:
    safe = str(text).replace('"', '\\"')
    return f'"{safe}"'


def _build_frontmatter(
    *,
    vanity: str,
    sale_name: str,
    min_discount: int,
    wishlist_count: int,
    deals_count: int,
    top_picks_count: int,
    generated_date: str,
) -> list[str]:
    return [
        "---",
        f"title: {_yaml_quote(f'Steam Wishlist Deals — {vanity}')}",
        f"profile: {_yaml_quote(vanity)}",
        f"sale_name: {_yaml_quote(sale_name)}",
        f"generated_date: {_yaml_quote(generated_date)}",
        f"min_discount: {int(min_discount)}",
        f"wishlist_count: {int(wishlist_count)}",
        f"deals_count: {int(deals_count)}",
        f"top_picks_count: {int(top_picks_count)}",
        "tags:",
        "  - steam-deals",
        "  - wishlist",
        "  - markdown-export",
        "---",
        "",
    ]


def _prio_badge(priority: int) -> str:
    if priority == 0:
        return ""
    if priority <= 10:
        return f" **#{priority}**"
    if priority <= 50:
        return f" #{priority}"
    return ""


def format_deal_row(game: dict, show_storefront: bool = False) -> str:
    pct = f"-{game['discount']}%"
    name = _link(game["steam_name"], game["appid"])
    if (
        game["score"] < 0.95
        and game["hltb_title"].lower() != game["steam_name"].lower()
    ):
        name += f" _(HLTB: {_md_esc(game['hltb_title'])})_"
    pph = game.get("price_per_hour")
    pph_str = f" · ${pph:.1f}/h" if pph is not None else ""
    hours = game.get("hours")
    hours_str = f" · {hours:.0f}h" if hours else ""
    extra = f"{hours_str}{pph_str}" if (hours_str or pph_str) else ""

    if show_storefront:
        return (
            f"| {pct} | {game['price']}{extra} | {game['storefront'] or '?'} | {name} |"
        )
    return f"| {pct} | {game['price']}{extra} | {game['price_original']} | {name} |"


def generate_md(
    deals: list[dict],
    backlog_on_sale: list[dict],
    have_on_sale: list[dict],
    vanity: str,
    owned: dict[str, str],
    wishlist_appids: list[str],
    min_discount: int,
    genres: list[str],
    hltb_used: bool = False,
    family_appids: set[str] | None = None,
    sale_name: str = "",
    priorities: dict[str, int] | None = None,
    historical_lows: dict[str, dict] | None = None,
    previous_appids: set[str] | None = None,
    reviews: dict[str, dict] | None = None,
    deck_compat: dict[str, int] | None = None,
    current_prices: dict[str, dict] | None = None,
    top_picks: list[dict] | None = None,
    comparison: dict | None = None,
    sort_field: str = "discount",
    tags_data: dict[str, dict] | None = None,
    local_trends: dict[str, dict] | None = None,
    active_bundles: dict[str, list[dict]] | None = None,
    protondb_data: dict[str, dict] | None = None,
    anticheat_data: dict[str, dict] | None = None,
    achievements_data: dict[str, dict] | None = None,
    watchlist_alerts: list[dict] | None = None,
    budget_result: dict | None = None,
    compare_data: dict | None = None,
    gift_ideas: list[dict] | None = None,
    include_frontmatter: bool = False,
    *,
    group_by_tier,
    filter_by_genres,
    group_deals_by_tag,
    linux_badge,
    multiplayer_badges,
    get_top_tags,
    players_badge,
    format_trend,
    achievements_badge,
    compute_value_score,
) -> str:
    today_obj = date.today()
    today = f"{today_obj.day} de {MESES[today_obj.month]} de {today_obj.year}"
    priorities = priorities or {}
    historical_lows = historical_lows or {}
    previous_appids = previous_appids or set()
    reviews = reviews or {}
    deck_compat_data = deck_compat or {}
    tags_data = tags_data or {}
    protondb_data = protondb_data or {}
    anticheat_data = anticheat_data or {}
    achievements_data = achievements_data or {}
    local_trends = local_trends or {}
    active_bundles_data = active_bundles or {}
    current_prices = current_prices or {}
    top_picks = top_picks or []
    watchlist_alerts = watchlist_alerts or []
    comp = comparison or {}
    owned_and_wishlisted = sorted(
        [(a, owned[a]) for a in set(owned) & set(wishlist_appids)],
        key=lambda x: x[1].lower(),
    )

    otras = familia = steam_sf = sin_sf = []
    if hltb_used:
        family_appids = family_appids or set()
        otras = [
            g
            for g in backlog_on_sale
            if g["storefront"]
            and g["storefront"].lower() not in ("steam", "")
            and not g["in_family"]
        ]
        familia = [g for g in backlog_on_sale if g["in_family"]]
        steam_sf = [
            g
            for g in backlog_on_sale
            if g["storefront"].lower() == "steam" and not g["in_family"]
        ]
        sin_sf = [
            g for g in backlog_on_sale if not g["storefront"] and not g["in_family"]
        ]

    sale_line = f"Evento: 🏷️ **{sale_name}** | " if sale_name else ""
    lines = [
        f"# Steam Wishlist Deals — {vanity}",
        f"> {sale_line}{today} | Precios en MXN | Perfil: {vanity.lower()}",
        f"> Wishlist: {len(wishlist_appids):,} juegos | Deals (≥{min_discount}%): {len(deals):,}"
        + (f" | Backlog en oferta: {len(backlog_on_sale)}" if hltb_used else ""),
    ]
    delta_parts = []
    new_deal_count = len(comp.get("new_deals", set()))
    disappeared_count = len(comp.get("disappeared", []))
    price_drops = sum(
        1 for v in comp.get("price_changes", {}).values() if v["direction"] == "down"
    )
    if new_deal_count:
        delta_parts.append(f"🆕 {new_deal_count} nuevos")
    if disappeared_count:
        delta_parts.append(f"❌ {disappeared_count} terminaron")
    if price_drops:
        delta_parts.append(f"⬇️ {price_drops} bajaron de precio")
    if delta_parts:
        lines.append(f"> {' · '.join(delta_parts)}")
    lines += ["", "---", ""]

    if include_frontmatter:
        lines = (
            _build_frontmatter(
                vanity=vanity,
                sale_name=sale_name,
                min_discount=min_discount,
                wishlist_count=len(wishlist_appids),
                deals_count=len(deals),
                top_picks_count=len(top_picks),
                generated_date=today_obj.isoformat(),
            )
            + lines
        )

    if top_picks:
        lines += [
            "## 🏆 Top 10 Picks",
            "",
            "> Ranking: reviews (26%) + descuento (22%) + prioridad (18%) + $/hora HLTB (14%) + Deck (10%) + Metacritic (5%) + edad (5%).",
            "",
            "| # | Score | % | Precio | Año | Reviews | MC | Deck/Linux | Modo | Juego |",
            "|---|-------|---|--------|-----|---------|----|-----------|----|-------|",
        ]
        for idx, tp in enumerate(top_picks, 1):
            rev = tp.get("review")
            rev_str = f"{rev['desc']} ({rev['pct']}%)" if rev else "—"
            tp_dk = tp.get("deck", 0)
            tp_pdb = protondb_data.get(tp["appid"])
            tp_ac = anticheat_data.get(tp["appid"])
            dk_str = linux_badge(tp_dk, tp_pdb, tp_ac, tp.get("linux_native", False))
            mc = tp.get("metacritic_score")
            mc_str = str(mc) if mc else "—"
            mp_str = multiplayer_badges(tp.get("categories", [])) or "—"
            prio = _prio_badge(tp.get("priority", 0))
            name_col = f"{_link(tp['name'], tp['appid'])}{prio}"
            yr = tp.get("release_year") or "—"
            lines.append(
                f"| {idx} | {tp['score']} | -{tp['discount']}% | {tp['price_final']} | {yr} | {rev_str} | {mc_str} | {dk_str} | {mp_str} | {name_col} |"
            )
        if any(tp.get("recommendation") or tp.get("score_reasons") for tp in top_picks):
            lines += ["", "### ¿Por qué salió arriba?", ""]
            for idx, tp in enumerate(top_picks, 1):
                recommendation = tp.get("recommendation")
                reasons = " · ".join(
                    _md_esc(reason) for reason in tp.get("score_reasons", [])
                )
                bullet = f"- {idx}. {_link(tp['name'], tp['appid'])}"
                if recommendation:
                    bullet += f" — **{_md_esc(recommendation)}**"
                if reasons:
                    bullet += f" · {reasons}"
                lines.append(bullet)
        lines += ["", "---", ""]

    if watchlist_alerts:
        lines += [
            "## 🎯 Watchlist Alerts",
            "",
            f"> **{len(watchlist_alerts)} juegos** de tu watchlist alcanzaron el precio objetivo.",
            "",
            "| Juego | Precio Actual | Objetivo | Descuento | Ahorro extra |",
            "|-------|---------------|----------|-----------|--------------|",
        ]
        for wa in watchlist_alerts:
            savings = wa["target_price"] - (wa["price_raw"] / 100)
            savings_str = f"${savings:.0f}" if savings > 0 else "—"
            lines.append(
                f"| {_link(wa['name'], wa['appid'])} | {wa['price_final']} | ${wa['target_price']:.0f} | -{wa['discount']}% | {savings_str} |"
            )
        lines += ["", "---", ""]

    if budget_result:
        b = budget_result
        lines += [
            f"## 💰 Budget Mode — ${b['budget']:.0f} MXN",
            "",
            f"> Con **${b['budget']:.0f} MXN** puedes comprar **{b['games_count']} juegos**.",
            f"> Total: ${b['total_spent']:.0f} | Ahorro vs original: ${b['total_savings']:.0f} | Restante: ${b['remaining']:.0f}",
            "",
            "| # | Score | % | Precio | Juego |",
            "|---|-------|---|--------|-------|",
        ]
        for idx, pick in enumerate(b["selected"], 1):
            label = _link(pick["name"], pick["appid"])
            recommendation = pick.get("recommendation")
            reasons = " · ".join(
                _md_esc(reason) for reason in pick.get("score_reasons", [])
            )
            if recommendation:
                label += f"<br>**{_md_esc(recommendation)}**"
            if reasons:
                label += f"<br>{reasons}"
            lines.append(
                f"| {idx} | {pick.get('score', '—')} | -{pick['discount']}% | {pick['price_final']} | {label} |"
            )
        lines += ["", "---", ""]

    if compare_data:
        friend = compare_data.get("friend_vanity", "?")
        overlap = compare_data.get("overlap", set())
        lines += [
            f"## 👥 Wishlist Comparison — {friend}",
            "",
            f"> **{len(overlap)} juegos en común** entre tu wishlist y la de {friend}.",
            "",
        ]
        overlap_deals = [d for d in deals if d["appid"] in overlap]
        if overlap_deals:
            lines += [
                f"### En común y en oferta ({len(overlap_deals)} juegos)",
                "",
                "| % | Precio | Juego |",
                "|---|--------|-------|",
            ]
            for d in sorted(overlap_deals, key=lambda x: -x["discount"])[:20]:
                lines.append(
                    f"| -{d['discount']}% | {d['price_final']} | {_link(d['name'], d['appid'])} |"
                )
            lines.append("")
        if gift_ideas:
            lines += [
                f"### 🎁 Gift Ideas para {friend} ({len(gift_ideas)} juegos)",
                "",
                f"> Juegos que {friend} quiere, están en oferta, y tú no los tienes.",
                "",
                "| % | Precio | Juego |",
                "|---|--------|-------|",
            ]
            for g in gift_ideas[:20]:
                lines.append(
                    f"| -{g['discount']}% | {g['price_final']} | {_link(g['name'], g['appid'])} |"
                )
        lines += ["", "---", ""]

    if active_bundles_data:
        bundles_grouped: dict[str, dict] = {}
        for appid, bundle_list in active_bundles_data.items():
            for b in bundle_list:
                key = b["title"]
                if key not in bundles_grouped:
                    bundles_grouped[key] = {**b, "appids": []}
                bundles_grouped[key]["appids"].append(appid)
        lines += [
            "## 📦 Bundles Activos",
            "",
            f"> **{len(bundles_grouped)} bundle(s)** activos con juegos de tu wishlist.",
            "",
        ]
        for bname, binfo in bundles_grouped.items():
            price_str = (
                f"${binfo['price']:.0f} {binfo['currency']}"
                if binfo["price"]
                else "Gratis"
            )
            link = (
                f"[{binfo['store']}]({binfo['url']})"
                if binfo.get("url")
                else binfo["store"]
            )
            lines += [
                f"### 📦 {bname}",
                f"> {price_str} en {link}",
                "",
                "| Juego | Precio Steam |",
                "|-------|-------------|",
            ]
            for aid in binfo["appids"]:
                deal = next((d for d in deals if d["appid"] == aid), None)
                if deal:
                    lines.append(
                        f"| {_link(deal['name'], aid)} | {deal['price_final']} |"
                    )
            lines.append("")
        lines += ["---", ""]

    if hltb_used:
        backlog_display = familia + sin_sf
        if backlog_display:
            lines += [
                "## Backlog en Oferta — Ya los Tienes en HLTB",
                "",
                f"> **{len(backlog_display)} juegos** de tu backlog de HLTB están en oferta en tu wishlist.",
                "",
            ]
            for emoji, subtitle, group in [
                ("🟡", "Confirmado en Familia de Steam", familia),
                ("🟢", "Sin plataforma registrada en HLTB", sin_sf),
            ]:
                if not group:
                    continue
                lines += [
                    f"### {emoji} {subtitle} ({len(group)} juegos)",
                    "",
                    "| % | Precio | HLTB en | Juego |",
                    "|---|--------|---------|-------|",
                ]
                for g in sorted(group, key=lambda x: -x["discount"]):
                    lines.append(format_deal_row(g, show_storefront=True))
                lines.append("")

    if genres:
        genre_deals = filter_by_genres(deals, genres)
        genre_label = ", ".join(genres)
        lines += [
            "---",
            "",
            f"## Genre Deals — {genre_label}",
            "",
            f"> **{len(genre_deals)} juegos** en oferta que coinciden con: _{genre_label}_.",
            "",
        ]
        if genre_deals:
            lines += ["| % | Precio | Era | Juego |", "|---|--------|-----|-------|"]
            for d in genre_deals:
                lines.append(
                    f"| -{d['discount']}% | {d['price_final']} | {d['price_original']} | {_link(d['name'], d['appid'])} |"
                )
        else:
            lines.append(
                "_Ningún juego de tu wishlist en oferta coincide con esos géneros._"
            )
        lines.append("")

    if tags_data:
        tag_groups = group_deals_by_tag(deals, tags_data)
        if tag_groups:
            lines += ["---", "", "## Deals por Tag", ""]
            for tag_name, tag_deals in tag_groups:
                lines += [
                    f"### {tag_name} ({len(tag_deals)} juegos)",
                    "",
                    "| % | Precio | Juego |",
                    "|---|--------|-------|",
                ]
                for d in sorted(tag_deals, key=lambda x: -x["discount"])[:10]:
                    lines.append(
                        f"| -{d['discount']}% | {d['price_final']} | {_link(d['name'], d['appid'])} |"
                    )
                lines.append("")

    lines += [
        "---",
        "",
        "## Quitar de la Wishlist",
        "",
        "> Limpieza: juegos que siguen en tu wishlist pero ya no deberían estar ahí.",
        "",
        "### Ya comprados en Steam (Steam no siempre los quita automáticamente)",
        "",
    ]
    if owned_and_wishlisted:
        lines += ["| AppID | Nombre |", "|-------|--------|"]
        for appid, name in owned_and_wishlisted:
            lines.append(f"| {appid} | {_link(name, appid)} |")
    else:
        lines.append("_Ninguno encontrado._")

    if hltb_used:
        if otras:
            lines += [
                "",
                f"### 🔴 Otra plataforma — GOG, Epic, Amazon… ({len(otras)} juegos)",
                "",
                "> Ya los tienes en otra plataforma según HLTB. Considera quitarlos de la wishlist.",
                "",
                "| % | Precio | HLTB en | Juego |",
                "|---|--------|---------|-------|",
            ]
            for g in sorted(otras, key=lambda x: -x["discount"]):
                lines.append(format_deal_row(g, show_storefront=True))

        if steam_sf:
            lines += [
                "",
                f"### ⚠️ Steam en HLTB — no localizado en familia ({len(steam_sf)} juegos)",
                "",
                "> HLTB dice que los tienes en Steam, pero no aparecen en tu biblioteca familiar.",
                "",
                "| % | Precio | HLTB en | Juego |",
                "|---|--------|---------|-------|",
            ]
            for g in sorted(steam_sf, key=lambda x: -x["discount"]):
                lines.append(format_deal_row(g, show_storefront=True))

        lines += [
            "",
            "### Completados / Retirados en HLTB en oferta en la Wishlist",
            "",
        ]
        if have_on_sale:
            lines += [
                "| % | Precio | Estado | Juego |",
                "|---|--------|--------|-------|",
            ]
            for g in have_on_sale:
                lines.append(
                    f"| -{g['discount']}% | {g['price']} | {g['status']} | {_link(g['steam_name'], g['appid'])} |"
                )
        else:
            lines.append("_Ninguno encontrado._")

    current_year = date.today().year
    cleanup_neg = [
        (d, reviews.get(d["appid"]))
        for d in deals
        if (r := reviews.get(d["appid"])) and r.get("pct", 100) < 50
    ]
    cleanup_always = [
        (d, local_trends.get(d["appid"]))
        for d in deals
        if (t := local_trends.get(d["appid"])) and t.get("times_on_sale", 0) >= 5
    ]
    cleanup_nolinux = [
        d
        for d in deals
        if deck_compat_data.get(d["appid"], 0) == 1
        and (p := protondb_data.get(d["appid"]))
        and p.get("tier") == "borked"
    ]
    cleanup_ac = [
        (d, anticheat_data.get(d["appid"]))
        for d in deals
        if (a := anticheat_data.get(d["appid"]))
        and a.get("status") in ("Denied", "Broken")
    ]
    cleanup_old = [
        (d, d.get("release_year"))
        for d in deals
        if d.get("release_year")
        and (current_year - d["release_year"]) > 8
        and d["discount"] < 70
    ]

    if cleanup_neg:
        cleanup_neg.sort(key=lambda x: x[1]["pct"])
        lines += [
            "",
            f"### 👎 Reviews muy negativas ({len(cleanup_neg)} juegos)",
            "",
            "> Estos juegos tienen reviews negativas, ¿seguro que los quieres?",
            "",
            "| % | Precio | Reviews | Juego |",
            "|---|--------|---------|-------|",
        ]
        for d, rev in cleanup_neg:
            lines.append(
                f"| -{d['discount']}% | {d['price_final']} | {rev['desc']} ({rev['pct']}%) | {_link(d['name'], d['appid'])} |"
            )

    if cleanup_always:
        cleanup_always.sort(key=lambda x: -x[1]["times_on_sale"])
        lines += [
            "",
            f"### 🔄 Siempre en oferta ({len(cleanup_always)} juegos)",
            "",
            "> Estos juegos están siempre en oferta, no hay prisa.",
            "",
            "| % | Precio | Veces | Prom. | Juego |",
            "|---|--------|-------|-------|-------|",
        ]
        for d, trend in cleanup_always:
            lines.append(
                f"| -{d['discount']}% | {d['price_final']} | {trend['times_on_sale']}x | {trend.get('avg_fmt', '?')} | {_link(d['name'], d['appid'])} |"
            )

    if cleanup_nolinux:
        lines += [
            "",
            f"### 🐧 Sin soporte Linux/Deck ({len(cleanup_nolinux)} juegos)",
            "",
            "> ProtonDB Borked + Deck Unsupported.",
            "",
            "| % | Precio | Juego |",
            "|---|--------|-------|",
        ]
        for d in sorted(cleanup_nolinux, key=lambda x: -x["discount"]):
            lines.append(
                f"| -{d['discount']}% | {d['price_final']} | {_link(d['name'], d['appid'])} |"
            )

    if cleanup_ac:
        lines += [
            "",
            f"### ⛔ Anti-cheat no funciona en Linux ({len(cleanup_ac)} juegos)",
            "",
            "> Anti-cheat status Denied o Broken en Linux.",
            "",
            "| % | Precio | Anti-Cheat | Status | Juego |",
            "|---|--------|------------|--------|-------|",
        ]
        for d, ac in cleanup_ac:
            ac_names = ", ".join(ac.get("anticheats", []))
            lines.append(
                f"| -{d['discount']}% | {d['price_final']} | {ac_names} | {ac['status']} | {_link(d['name'], d['appid'])} |"
            )

    if cleanup_old:
        cleanup_old.sort(key=lambda x: (x[1], -x[0]["discount"]))
        lines += [
            "",
            f"### 🕰️ Juego viejo, descuento bajo ({len(cleanup_old)} juegos)",
            "",
            "> Juegos de más de 8 años con menos de 70% de descuento. Suelen bajar más.",
            "",
            "| % | Precio | Año | Juego |",
            "|---|--------|-----|-------|",
        ]
        for d, year in cleanup_old:
            lines.append(
                f"| -{d['discount']}% | {d['price_final']} | {year} | {_link(d['name'], d['appid'])} |"
            )

    lines += ["", "---", ""]

    disappeared = comp.get("disappeared", [])
    if disappeared:
        lines += [
            f"## ❌ Ofertas Terminadas ({len(disappeared)} juegos)",
            "",
            "> Juegos que estaban en oferta el run anterior pero ya no.",
            "",
            "| % | Último precio | Juego |",
            "|---|---------------|-------|",
        ]
        for dd in disappeared:
            lines.append(
                f"| -{dd['discount']}% | {dd['price_final']} | {_link(dd['name'], dd['appid'])} |"
            )
        lines += ["", "---", ""]

    has_itad = bool(historical_lows)
    has_best_prices = bool(current_prices)
    for tier_name, tier_deals in group_by_tier(deals):
        sort_keys = {
            "discount": lambda d: -d["discount"],
            "price": lambda d: d.get("price_raw", 0),
            "reviews": lambda d: -(reviews.get(d["appid"], {}).get("pct", 0)),
            "priority": lambda d: (
                priorities.get(d["appid"], 0) == 0,
                priorities.get(d["appid"], 9999),
            ),
            "score": lambda d: (
                -(
                    compute_value_score(
                        d["discount"],
                        reviews.get(d["appid"], {}).get("pct"),
                        priorities.get(d["appid"], 0),
                        None,
                        deck_compat_data.get(d["appid"], 0),
                        release_year=d.get("release_year"),
                        metacritic_score=d.get("metacritic_score"),
                    )
                )
            ),
        }
        tier_deals.sort(key=sort_keys.get(sort_field, sort_keys["discount"]))

        lines += [
            f"## {tier_name} de Descuento ({len(tier_deals)} juegos)",
            "",
        ]

        has_tags = bool(tags_data)
        has_ach = bool(achievements_data)
        header = "| | % | Precio | Era | Año | Reviews | MC | Deck/Linux | Modo"
        sep = "|-|---|--------|-----|-----|---------|----|-----------|----|"
        if has_ach:
            header += " | Logros"
            sep += "|-------"
        if has_tags:
            header += " | Tags"
            sep += "|------"
        if has_itad:
            header += " | Min. hist."
            sep += "|------------"
        if has_best_prices:
            header += " | Mejor precio"
            sep += "|--------------"
        has_trends = bool(local_trends)
        if has_trends:
            header += " | Tendencia"
            sep += "|-----------"
        header += " | Juego |"
        sep += "|-------|"
        lines += [header, sep]

        for d in tier_deals:
            markers = []
            appid = d["appid"]
            if appid in comp.get("new_deals", set()):
                markers.append("🆕")
            pc = comp.get("price_changes", {}).get(appid)
            if pc:
                markers.append(
                    f"⬇️ -{pc['delta_str']}"
                    if pc["direction"] == "down"
                    else f"⬆️ +{pc['delta_str']}"
                )
            streak = comp.get("deal_streak", {}).get(appid, 0)
            if streak >= 3:
                markers.append(f"🔥 {streak}º run")
            if (
                not markers
                and not comp
                and previous_appids
                and appid not in previous_appids
            ):
                markers.append("🆕")
            new_marker = " ".join(markers)
            prio = _prio_badge(priorities.get(d["appid"], 0))
            name_col = f"{_link(d['name'], d['appid'])}{prio}"

            rev = reviews.get(d["appid"])
            rev_str = f"{rev['desc']} ({rev['pct']}%)" if rev else "—"

            dk = deck_compat_data.get(d["appid"], 0)
            pdb = protondb_data.get(d["appid"])
            ac = anticheat_data.get(d["appid"])
            dk_str = linux_badge(dk, pdb, ac, d.get("linux_native", False))

            mc = d.get("metacritic_score")
            mc_str = str(mc) if mc else "—"
            mp_str = multiplayer_badges(d.get("categories", [])) or "—"

            year_str = str(d.get("release_year", "")) if d.get("release_year") else "—"
            row = f"| {new_marker} | -{d['discount']}% | {d['price_final']} | {d['price_original']} | {year_str} | {rev_str} | {mc_str} | {dk_str} | {mp_str}"
            if has_ach:
                ach = achievements_data.get(d["appid"])
                row += f" | {achievements_badge(ach)}"
            if has_tags:
                top_t = get_top_tags(tags_data, d["appid"], n=3)
                tags_str = " ".join(f"`{t}`" for t in top_t) if top_t else "—"
                pb = players_badge(tags_data.get(d["appid"], {}))
                if pb:
                    tags_str += f" {pb}"
                row += f" | {tags_str}"

            if has_itad:
                low = historical_lows.get(d["appid"])
                low_str = f"${low['price']:.0f} ({low['date']})" if low else "—"
                row += f" | {low_str}"

            if has_best_prices:
                bp = current_prices.get(d["appid"])
                bp_str = (
                    f"${bp['price']:.0f} en [{bp['store']}]({bp['url']})" if bp else "—"
                )
                row += f" | {bp_str}"

            if has_trends:
                trend = local_trends.get(d["appid"])
                row += f" | {format_trend(trend)}" if trend else " | —"

            row += f" | {name_col} |"
            lines.append(row)
        lines += ["", "---", ""]

    return "\n".join(lines)

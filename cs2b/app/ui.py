"""LANTERN frontend: a step-by-step walkthrough of the pipeline.

Start from inside cs2b:  streamlit run app/ui.py
Set LANTERN_API if the backend is not on http://localhost:8000.
"""
import os
import re

import altair as alt
import pandas as pd
import requests
import streamlit as st

API = os.environ.get("LANTERN_API", "http://localhost:8000").rstrip("/")
TIMEOUT = 1800
SEC_PAGE = "https://www.sec.gov/data-research/sec-markets-data/bdc-data-sets"
STEPS = ["Source", "Read", "Clean", "Compare", "Final list", "Check by hand"]
NUM = ["①", "②", "③", "④", "⑤", "⑥"]
RELEASE_RE = re.compile(r"\d{4}(?:_(?:0[1-9]|1[0-2])|q[1-4])")

st.set_page_config(page_title="LANTERN look-through", page_icon="🔦", layout="wide")
st.markdown("""<style>
section[data-testid="stSidebar"] div[role="radiogroup"] label p {font-size: 1.2rem; font-weight: 500;}
section[data-testid="stSidebar"] div[role="radiogroup"] label {padding: 4px 0;}
</style>""", unsafe_allow_html=True)

RULE_TEXT = {
    "rule_totals": "Total and subtotal lines, like 'Total investments'. They are sums, not loans.",
    "rule_cash": "Cash and money-market lines, when the fund does not count them as investments.",
    "rule_commitment_rows": "Promise lines: money promised but not lent yet.",
    "rule_jv_portfolio": "Loans owned by a joint venture, listed by the fund for information only.",
    "rule_issuer_subtotals": "Company-level lines that only add up that company's loans.",
    "rule_rollforward_copies": "Loans repeated from the affiliate roll-forward table.",
    "clear_equity_principal": "Not removed: equity lines whose 'principal' is really a count of units. "
                              "The principal is cleared, the line stays.",
}


# ---------------------------------------------------------------- backend
def call(method, path, raw=False, **kw):
    try:
        r = requests.request(method, f"{API}{path}", timeout=TIMEOUT, **kw)
    except requests.ConnectionError:
        st.error(f"Cannot reach the backend at {API}. Start it with: uvicorn app.api:app --port 8000")
        st.stop()
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text)
        except ValueError:
            detail = r.text[:2000]
        st.error(f"Backend error {r.status_code}: {detail}")
        st.stop()
    return r.text if raw else r.json()


@st.cache_data(ttl=600, show_spinner=False)
def cached(path, params_json="{}", raw=False):
    """Backend answers are remembered per path and filters, so reruns stay fast."""
    import json as _json
    return call("GET", path, raw=raw, params=_json.loads(params_json))


def get(path, params=None, raw=False):
    import json as _json
    clean = {k: v for k, v in (params or {}).items() if v is not None}
    return cached(path, _json.dumps(clean, sort_keys=True), raw)


@st.cache_data(ttl=600)
def get_config():
    return call("GET", "/config")


@st.cache_data(ttl=600)
def get_source():
    return call("GET", "/source")


def money(x):
    return "n/a" if x is None or pd.isna(x) else f"${x / 1e9:,.1f}B"


def esc(text):
    """Show $ as a dollar sign, not as the start of a maths formula."""
    return str(text).replace("$", "\\$")


def nice(rule):
    return rule.removeprefix("rule_").replace("_", " ")


cfg, src = get_config(), get_source()
ALL_RULES = cfg["rules"]
DEFAULT_RELEASES = [r for r in cfg["default_releases"] if r in cfg["releases"]]
DEFAULT_TOL = float(cfg["default_tolerance"] * 100)
ss = st.session_state

# keep settings alive while their widgets are hidden in a folded step
KEYS = ["rels", "tol"] + [f"rule_{r}" for r in ALL_RULES]
if "rels" not in ss:
    ss.rels, ss.tol, ss.step = list(DEFAULT_RELEASES), DEFAULT_TOL, 1
    for r in ALL_RULES:
        ss[f"rule_{r}"] = r in cfg["default_rules"]
for k in KEYS:
    ss[k] = ss[k]
ss.q = ss.get("q", "")
if ss.get("add_rel"):
    new_rels = list(ss.pop("add_rel"))
    ss.rels = sorted(set(ss.rels) | set(new_rels))
    st.toast(f"Added {', '.join(new_rels)}. Now selected in step ①.")
if ss.get("drop_rel"):
    gone = ss.pop("drop_rel")
    ss.rels = [r for r in ss.rels if r != gone] or list(DEFAULT_RELEASES)
    st.toast(f"Removed {gone}.")


def chosen_rules():
    return [r for r in ALL_RULES if ss[f"rule_{r}"]]


def settings_now():
    return {"releases": sorted(ss.rels), "tolerance": round(ss.tol / 100, 6), "rules": chosen_rules()}


def go_to(n):
    ss.step = n


def run_then(n):
    ss.pending = n


def preset(name):
    ss.rels, ss.tol = list(DEFAULT_RELEASES), DEFAULT_TOL
    for r in ALL_RULES:
        ss[f"rule_{r}"] = (r in cfg["default_rules"]) and name != "raw"
    ss.tol = {"strict": 0.1, "loose": 5.0}.get(name, DEFAULT_TOL)
    ss.pending = 4


def reset():
    for k in KEYS + ["run", "fil", "step"]:
        ss.pop(k, None)


# ---------------------------------------------------------------- run when a step asks for it
if ss.get("pending"):
    target = ss.pop("pending")
    if not ss.rels:
        st.error("Pick at least one month in step ①.")
        ss.step = 1
    else:
        with st.spinner("Working on the data (seconds from the pipeline cache, a few minutes "
                        "the first time a new set of months is read)"):
            if "baseline" not in ss:
                ss.baseline = call("POST", "/runs", json={})
                ss.base_fil = pd.DataFrame(call("GET", f"/runs/{ss.baseline['run_id']}/filings"))
            body = settings_now()
            ss.run = call("POST", "/runs", json=body)
            ss.fil = pd.DataFrame(call("GET", f"/runs/{ss.run['run_id']}/filings"))
        ss.step = target

run = ss.get("run")
is_default = run is not None and run["settings"] == ss.baseline["settings"]


def delta(now, before, fmt="{:+,}"):
    return None if is_default or before is None else fmt.format(now - before)


# ---------------------------------------------------------------- mode
with st.sidebar:
    st.title("🔦 LANTERN")
    mode = st.radio("Mode", ["🧭 How it's built", "🔎 Explore the loans"], key="mode",
                    label_visibility="collapsed")

    def do_refresh():
        call("POST", "/refresh")
        st.cache_data.clear()
        for k in ("baseline", "base_fil", "run", "fil"):
            ss.pop(k, None)

    st.button("↻ Refresh data", on_click=do_refresh, use_container_width=True,
              help="Reload the files on disk, for example after dvc pull or adding a month.")


def ensure_runs():
    if "baseline" not in ss:
        with st.spinner("Loading the loan list (seconds from the pipeline cache)"):
            ss.baseline = call("POST", "/runs", json={})
            ss.base_fil = pd.DataFrame(call("GET", f"/runs/{ss.baseline['run_id']}/filings"))
    if "run" not in ss:
        ss.run, ss.fil = ss.baseline, ss.base_fil


def millions(x):
    return None if x is None or pd.isna(x) else round(x / 1e6, 2)


def loan_table(rows):
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    def col(c):
        return df[c] if c in df else pd.Series([None] * len(df))

    def text(c):
        return col(c).fillna("").astype(str)

    num = lambda c: pd.to_numeric(col(c), errors="coerce")  # noqa: E731
    return pd.DataFrame({
        "Fund": text("name"), "Loan": text("identifier"), "Industry": text("industry"),
        "Value ($M)": (num("fair_value") / 1e6).round(2), "Owed ($M)": (num("principal") / 1e6).round(2),
        "Price (% of owed)": num("price"),
        "Check": col("check_currency").map(lambda x: "⚠ currency?" if x is True else ""),
        "Rate %": (num("interest_rate") * 100).round(2), "Maturity": text("maturity").str[:10],
        "Month": text("release"), "In final list": col("in_final").map({True: "yes", False: "no"}),
        "SEC rows": text("source_rows"), "Report": col("filing_url")})


LINK = {"Report": st.column_config.LinkColumn("Report", display_text="open ↗")}
KEEP_UPPER = {"LLC", "L.L.C.", "BDC", "LP", "L.P.", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX",
              "X", "XI", "XII", "USA", "US", "SBIC", "CLO", "TCW", "MSD", "SL", "LGAM", "OFS", "HPS",
              "KKR", "FS", "NMF", "AB", "PGIM", "BC", "TPG", "MSC", "SCP", "SLR"}


def pretty(name):
    if not isinstance(name, str):
        return ""
    return " ".join(w if w.upper().strip(",.") in KEEP_UPPER or w.upper().strip(",") in KEEP_UPPER
                    else w.capitalize() for w in name.split())


def company_of(identifier):
    return re.split(r"\s*\|\s*|,", str(identifier or ""))[0].strip()


def fmt_m(x):
    return "n/a" if x is None or pd.isna(x) else f"${x / 1e6:,.1f}M"


def loan_card(r):
    with st.container(border=True):
        st.markdown(f"**{r['identifier']}**")
        st.caption(f"{pretty(r.get('name'))} · SEC file {r.get('release')} · report {r.get('adsh')} · "
                   f"SEC rows {r.get('source_rows')}")
        a, b, c, d = st.columns(4)
        a.metric("Value", fmt_m(r.get("fair_value")))
        b.metric("Owed", fmt_m(r.get("principal")))
        c.metric("Price", "n/a" if pd.isna(r.get("price")) else f"{r['price']:.1f}",
                 help="Value ÷ owed × 100. Below 100 means the fund values it below what is owed.")
        d.metric("Rate", "n/a" if pd.isna(r.get("interest_rate")) else f"{r['interest_rate'] * 100:.2f}%")
        bits = [("Spread " + f"{r['spread'] * 100:.2f}%") if pd.notna(r.get("spread")) else "",
                ("Matures " + str(r["maturity"])[:10]) if pd.notna(r.get("maturity")) else "",
                ("Industry " + str(r["industry"])) if pd.notna(r.get("industry")) else "",
                "Loan" if r.get("is_debt") else "Equity or other",
                "In the final list" if r.get("in_final") else "Report does not add up, not in final list"]
        st.caption(" · ".join(b for b in bits if b))
        if r.get("check_currency"):
            st.warning("Price above 110: the amount owed is probably in another currency. Check the report.")
        l, rr = st.columns(2)
        if r.get("filing_url"):
            l.link_button("Open the report on SEC.gov ↗", r["filing_url"], use_container_width=True)
        rr.button(f"Find {company_of(r['identifier'])[:30]} in all funds", on_click=set_q,
                  args=(company_of(r["identifier"]),), use_container_width=True, key=f"find_{r.get('source_rows')}")


def show_loans(rows, key, sort_price=False, height=360):
    raw = pd.DataFrame(rows)
    if raw.empty:
        st.info("No loans to show.")
        return
    if sort_price:
        raw = raw.sort_values("price", na_position="last")
    raw = raw.reset_index(drop=True)
    disp = loan_table(raw.to_dict("records"))
    disp["Fund"] = disp["Fund"].map(pretty)
    cols = ["Fund", "Loan", "Value ($M)", "Owed ($M)", "Price (% of owed)", "Rate %", "Maturity", "Report"]
    if disp["Check"].ne("").any():
        cols.insert(5, "Check")
    if st.toggle("Show technical columns", key=f"tech_{key}"):
        cols += ["Industry", "Month", "In final list", "SEC rows"]
    ev = st.dataframe(
        disp[cols], hide_index=True, use_container_width=True, height=height, key=f"tbl_{key}",
        on_select="rerun", selection_mode="single-row",
        column_config={**LINK,
                       "Value ($M)": st.column_config.NumberColumn(format="%.1f"),
                       "Owed ($M)": st.column_config.NumberColumn(format="%.1f"),
                       "Rate %": st.column_config.NumberColumn(format="%.2f"),
                       "Price (% of owed)": st.column_config.ProgressColumn(
                           "Price (% of owed)", min_value=0, max_value=120, format="%.1f")})
    picked = ev.selection.rows if ev and ev.selection else []
    if picked:
        loan_card(raw.iloc[picked[0]].to_dict())
    else:
        st.caption("Click a row to see that loan's details.")


def show_fund(adsh):
    d = get(f"/runs/{ss.run['run_id']}/filings/{adsh}/holdings")
    f, tol_ = d["filing"], ss.run["settings"]["tolerance"]
    st.subheader(pretty(f["name"]))
    st.caption(f"{f['form']} for the period ending {str(f['period'])[:10]} · SEC file {f['release']} · "
               f"report number (adsh) {f['adsh']} · {f['n_holdings']:,} loans kept")
    a, b, c = st.columns(3)
    a.metric("Our sum of its loans", money(f["holdings_fv"]))
    b.metric("Total the fund reported", money(f["filed_fv"]))
    c.metric("Gap", "n/a" if f["gap_pct"] is None else f"{f['gap_pct']:+.2%}")
    if f["gap_pct"] is None:
        st.warning("No usable total or no loans, so there is nothing to compare.")
    elif f["admitted"]:
        st.success(f"Adds up within {tol_:.1%}: its {f['n_holdings']:,} loans are in the final list.")
    else:
        st.error(f"Does not add up within {tol_:.1%}, so it is left out. Reason: {f['triage_category']}.")
    if f.get("filing_url"):
        st.link_button("Open the original report on SEC.gov ↗", f["filing_url"])
    h = pd.DataFrame(d["holdings"])
    if not h.empty:
        with st.expander(f"Show its {len(h):,} loans (largest first)"):
            st.dataframe(h.drop(columns=["filing_url"], errors="ignore"), hide_index=True,
                         use_container_width=True)


def report_status(fil, key):
    """Fund reports whose totals match, and those that do not, as two tables. Click a row to check it."""
    if ss.run.get("triage_error"):
        st.warning(ss.run["triage_error"])
    ok = fil[fil["admitted"]].reset_index(drop=True)
    bad = fil[~fil["admitted"]].reset_index(drop=True)
    link = {"Report": st.column_config.LinkColumn("Report", display_text="open ↗")}
    t_ok, t_bad = st.tabs([f"✅ Totals match ({len(ok)})", f"❌ Totals do not match ({len(bad)})"])
    picked = None
    with t_ok:
        ev = st.dataframe(pd.DataFrame({
            "Fund": ok["name"].map(pretty), "Form": ok["form"], "Loans": ok["n_holdings"],
            "Our sum ($M)": (ok["holdings_fv"] / 1e6).round(1),
            "Fund's own total ($M)": (ok["filed_fv"] / 1e6).round(1),
            "Difference %": (ok["gap_pct"] * 100).round(2), "Report": ok["filing_url"]}),
            hide_index=True, use_container_width=True, key=f"ok_{key}", column_config=link,
            on_select="rerun", selection_mode="single-row")
        if ev and ev.selection.rows:
            picked = ok.iloc[ev.selection.rows[0]]["adsh"]
    with t_bad:
        todo = int(bad["triage_category"].eq("to_triage").sum())
        a, b, c = st.columns(3)
        a.metric("Totals do not match", f"{len(bad)}")
        b.metric("Reason written", f"{len(bad) - todo}")
        c.metric("Reason still missing", f"{todo}")
        ev = st.dataframe(pd.DataFrame({
            "Fund": bad["name"].map(pretty), "Form": bad["form"],
            "Difference %": (bad["gap_pct"] * 100).round(2), "Reason": bad["triage_category"],
            "Evidence": bad.get("triage_evidence"), "Example": bad.get("triage_example"),
            "Fix or why not": bad.get("triage_fix"), "Review": bad.get("triage_status"),
            "Report": bad["filing_url"]}),
            hide_index=True, use_container_width=True, key=f"bad_{key}", column_config=link,
            on_select="rerun", selection_mode="single-row")
        if ev and ev.selection.rows:
            picked = bad.iloc[ev.selection.rows[0]]["adsh"]
        with st.expander("Count per reason"):
            st.dataframe(bad["triage_category"].value_counts().rename_axis("Reason")
                         .reset_index(name="Fund reports"), hide_index=True, use_container_width=True)
        st.caption("Reasons come from data/triage.csv. Press Refresh data after it changes.")
    if picked:
        with st.container(border=True):
            show_fund(picked)
    else:
        st.caption("Click a fund in either table to see its check.")


def set_q(text):
    ss.q = text


if mode.startswith("🔎"):
    ensure_runs()
    run_, cov_ = ss.run, ss.run["coverage"]
    own = run_["settings"] != ss.baseline["settings"]
    st.title("🔦 LANTERN look-through")
    st.markdown(f"These are loans from the **{cov_['filings_admitted']} fund reports** (of "
                f"{cov_['filings_attempted']}) whose loans add up to the fund's own total. "
                f"They hold **{cov_['share_of_dollars']:.1%} of all the money** in the reports.")
    st.caption(("Your own settings from 'How it's built'. " if own else "Team default settings. ")
               + f"Allowed difference: {run_['settings']['tolerance']:.1%}.")
    t_over, t_search, t_fund, t_watch = st.tabs(
        ["📊 Overview", "🔎 Search", "🏦 Fund reports", "⚠️ Watch list"])
    ov = get(f"/runs/{run_['run_id']}/overview")

    with t_search:
        st.caption("Find every loan to a company, from every fund, and see how each fund values it.")
        st.text_input("Company, fund or industry", key="q", placeholder="Snoopy Bidco")
        ex = st.columns([1, 1, 1, 3])
        for col, word in zip(ex, ["Snoopy Bidco", "Ivy Hill", "MYOB"]):
            col.button(word, on_click=set_q, args=(word,), use_container_width=True)
        with st.expander("Filters"):
            f1, f2 = st.columns(2)
            debt_only = f1.toggle("Loans only (no equity)")
            include_all = f2.toggle("Include funds whose totals don't match (less reliable)",
                                    help="Off: only loans we could check against the fund's own total. "
                                         "On: also the others, marked 'In final list: no'.")
            inds = st.multiselect("Industries", ov["all_industries"])
            min_m = st.number_input("Minimum value ($M)", 0.0, 100000.0, 0.0, step=1.0)
        q = ss.get("q", "").strip()
        if not (q or inds or debt_only or min_m):
            st.caption("Type a name, or click one of the examples. Several words must all match.")
        else:
            params = {"q": q or None, "scope": "all" if include_all else "final",
                      "debt_only": debt_only, "industry": inds or None,
                      "min_fv": min_m * 1e6 if min_m else None}
            res = get(f"/runs/{run_['run_id']}/loans", params)
            looking = f'"{q}"' if q else "your filters"
            extra = [x for x in [("loans only" if debt_only else ""),
                                 ("including funds whose totals don't match" if include_all
                                  else "only funds whose totals match"),
                                 (", ".join(inds) if inds else ""),
                                 (f"at least ${min_m:,.0f}M" if min_m else "")] if x]
            st.subheader(f"Results for {looking}")
            st.caption(" · ".join(extra))
            a, b, c = st.columns(3)
            a.metric("Loans found", f"{res['count']:,}")
            b.metric("Funds holding them", f"{res['funds']}")
            c.metric("Total value", money(res["fair_value"]))
            if res["count"] == 0:
                st.info("Nothing found. Try one word, or open Filters and include funds whose totals don't match.")
            else:
                if res["funds"] > 1:
                    st.markdown("**Funds that hold it** (price = value ÷ owed × 100; 100 means worth what is owed)")
                    bf = pd.DataFrame(res["by_fund"]).reset_index(drop=True)
                    fev = st.dataframe(pd.DataFrame({
                        "Fund": bf["name"].map(pretty), "Loans": bf["loans"],
                        "Value ($M)": (bf["fair_value"] / 1e6).round(1),
                        "Owed ($M)": (bf["principal"] / 1e6).round(1), "Avg price": bf["avg_price"],
                        "In final list": bf["in_final"].map({True: "yes", False: "no"})}),
                        hide_index=True, use_container_width=True, key="tbl_funds",
                        on_select="rerun", selection_mode="single-row",
                        column_config={"Avg price": st.column_config.ProgressColumn(
                            "Avg price", min_value=0, max_value=120, format="%.1f")})
                    fpick = fev.selection.rows if fev and fev.selection else []
                    if fpick:
                        with st.container(border=True):
                            show_fund(bf.iloc[fpick[0]]["adsh"])
                    else:
                        st.caption("Click a fund to check its whole report.")
                st.markdown("**Every loan found**" + (" (largest 2,000 shown, the download has all)" if res["truncated"] else ""))
                show_loans(res["loans"], "search")
                key = (run_["run_id"], str(sorted(params.items())))
                if st.button("Prepare download (CSV)", key="dl_search"):
                    ss.dl_search = (key, get(f"/runs/{run_['run_id']}/loans.csv", params, raw=True))
                if ss.get("dl_search") and ss.dl_search[0] == key:
                    st.download_button("⬇ Download these results (CSV)", ss.dl_search[1],
                                       file_name=f"lantern_search_{(q or 'filters').replace(' ', '_')}.csv",
                                       mime="text/csv")
                st.caption("⚠ currency? = price above 110. Usually the amount owed is in pounds or euros "
                           "while the value is in dollars, so check the report before using the price.")

    with t_watch:
        st.caption("Loans the funds themselves value below what the company owes. The fund doubts "
                   "it will be paid back in full. Lower price = more doubt.")
        w1, w2 = st.columns(2)
        below = w1.slider("Show loans valued below (% of owed)", 50, 100, 90)
        min_w = w2.number_input("Minimum value ($M) ", 0.0, 100000.0, 1.0, step=1.0)
        params = {"debt_only": True, "price_hi": below, "min_fv": min_w * 1e6 if min_w else None}
        res = get(f"/runs/{run_['run_id']}/loans", params)
        st.caption(f"Showing: loans valued below {below}% of what is owed"
                   + (f", worth at least ${min_w:,.0f}M" if min_w else "") + ", final list only.")
        a, b, c = st.columns(3)
        a.metric("Loans", f"{res['count']:,}")
        b.metric("Funds", f"{res['funds']}")
        c.metric("Their value", money(res["fair_value"]))
        if res["count"]:
            show_loans(res["loans"], "watch", sort_price=True)
            wkey = (run_["run_id"], str(sorted(params.items())))
            if st.button("Prepare download (CSV)", key="dl_watch"):
                ss.dl_watch = (wkey, get(f"/runs/{run_['run_id']}/loans.csv", params, raw=True))
            if ss.get("dl_watch") and ss.dl_watch[0] == wkey:
                st.download_button("⬇ Download watch list (CSV)", ss.dl_watch[1],
                                   file_name=f"lantern_watch_below_{below}.csv", mime="text/csv")
        with st.expander(f"Prices that look wrong ({ov['check_currency']} loans above 110)"):
            st.caption("Usually the amount owed is in another currency. Check the report before using these.")
            odd = get(f"/runs/{run_['run_id']}/loans", {"debt_only": True, "price_lo": 110})
            show_loans(odd["loans"], "odd", height=260)

    with t_fund:
        st.caption("Every fund report, split by whether its loans add up to the fund's own total. "
                   "Click a fund to see its check and its loans.")
        report_status(ss.fil, "explore")

    with t_over:
        st.caption("The big picture of the checked loan list.")
        a, b, c, d = st.columns(4)
        a.metric("Loans in the final list", f"{ov['loans']:,}")
        b.metric("Funds", f"{ov['funds']}")
        c.metric("Total value", money(ov["fair_value"]))
        d.metric("In loans (the rest is company shares)", f"{ov['debt_share']:.0%}")
        l, r = st.columns(2)
        for col, key, field, title in [(l, "industries", "industry", "Biggest industries"),
                                       (r, "funds_top", "name", "Biggest funds")]:
            df = pd.DataFrame(ov[key])
            if not df.empty and field == "name":
                df["name"] = df["name"].map(pretty)
            if not df.empty:
                df["value"] = df["fair_value"] / 1e9
                col.markdown(f"**{title}** ($B)")
                col.altair_chart(alt.Chart(df).mark_bar(color="#3b82f6").encode(
                    x=alt.X("value:Q", title=None), y=alt.Y(f"{field}:N", sort="-x", title=None),
                    tooltip=[field, alt.Tooltip("value:Q", format=",.2f")]), use_container_width=True)
    st.stop()

# ---------------------------------------------------------------- sidebar: where you are
with st.sidebar:
    for i, name in enumerate(STEPS, start=1):
        mark = "✅" if i < ss.step else ("👉" if i == ss.step else "⬜")
        st.markdown(f"{mark} {NUM[i - 1]} {name}")
    st.button("↺ Start over", on_click=reset, use_container_width=True)
    with st.expander("Quick experiments"):
        st.caption("Jump straight to the result with one setting changed.")
        st.button("Team default", on_click=preset, args=("default",), use_container_width=True)
        st.button("No cleaning at all", on_click=preset, args=("raw",), use_container_width=True)
        st.button("Strict tolerance 0.1%", on_click=preset, args=("strict",), use_container_width=True)
        st.button("Loose tolerance 5%", on_click=preset, args=("loose",), use_container_width=True)
    st.caption("Settings you run here are also used in Explore.")

# ---------------------------------------------------------------- header
st.title("🔦 LANTERN look-through")
st.caption("Funds called BDCs lend to private companies and report every loan to the SEC each quarter. "
           "We turn those reports into one checked list of loans. Walk through it step by step.")
def pipeline_strip():
    """The whole pipeline as 6 boxes: done = green with its result, current = blue, future = grey."""
    r = run
    vals = [f"{len(ss.rels)} SEC files",
            f"{r['stats']['read']['current_holdings']:,} loans" if r else "?",
            f"{r['stats']['clean']['kept']:,} kept" if r else "?",
            f"{r['coverage']['filings_admitted']} of {r['coverage']['filings_attempted']} pass" if r else "?",
            f"{r['stats']['final']['loans']:,} loans" if r else "?",
            "by hand"]
    boxes = []
    for i, (name, val) in enumerate(zip(STEPS, vals), start=1):
        if i < ss.step:
            style, mark, shown = "border:1px solid #2e9e5b;background:rgba(46,158,91,0.12)", "✓ ", val
        elif i == ss.step:
            style, mark, shown = "border:2px solid #3b82f6;background:rgba(59,130,246,0.18)", "", (val if i == 1 or r else "?")
        else:
            style, mark, shown = "border:1px solid rgba(150,150,150,0.4);opacity:0.6", "", "?"
        boxes.append(f"<div style='flex:1;min-width:0;border-radius:10px;padding:10px 8px;text-align:center;{style}'>"
                     f"<div style='font-size:13px'>{mark}{NUM[i - 1]} {name}</div>"
                     f"<div style='font-size:18px;font-weight:600;margin-top:2px'>{shown}</div></div>")
    arrow = "<div style='align-self:center;font-size:20px;padding:0 4px'>→</div>"
    st.markdown("<div style='display:flex;gap:2px;margin:8px 0 4px'>" + arrow.join(boxes) + "</div>",
                unsafe_allow_html=True)
    st.caption(f"Step {ss.step} of 6: {STEPS[ss.step - 1]}")


pipeline_strip()
st.divider()


def done_row(n, text):
    """A finished step folds into one line, with a button to go back and change it."""
    with st.container(border=True):
        a, b = st.columns([6, 1])
        a.markdown(f"**{NUM[n - 1]} {STEPS[n - 1]}** · {text}")
        b.button("Change", key=f"back_{n}", on_click=go_to, args=(n,), use_container_width=True)


# ---------------------------------------------------------------- ① source
if ss.step == 1:
    with st.container(border=True):
        st.subheader("① Where the data comes from")
        st.markdown(f"The SEC publishes every fund's quarterly loan list as one ZIP file per month "
                    f"([BDC data sets]({SEC_PAGE})). Our quarter is April to June 2026.")
        rel_info = call("GET", "/releases")
        origin = {r["release"]: r["origin"] for r in rel_info}
        ss.rels = [r for r in ss.rels if r in origin]
        st.multiselect("Which months do you want to use?", list(origin), key="rels",
                       format_func=lambda r: r if origin[r] == "team data (DVC)" else f"{r} ({origin[r]})")
        if src["manifest_found"] and not src["mismatches"]:
            st.success("✓ These files match the fingerprints we recorded when we downloaded them.")
        elif src["mismatches"]:
            st.error(f"Fingerprint mismatch: {', '.join(src['mismatches'])}. Run dvc pull.")
        with st.expander("Show file details"):
            man = pd.DataFrame(src["files"])
            if not man.empty:
                st.dataframe(pd.DataFrame({
                    "File": man["path"], "Size (MB)": (man["bytes"] / 1e6).round(1),
                    "Fingerprint (SHA-256, first 16)": man["sha256"].str[:16],
                    "Downloaded from": man["url"]}), hide_index=True, use_container_width=True,
                    column_config={"Downloaded from": st.column_config.LinkColumn(display_text="SEC link")})
            st.caption("The files live in S3 through DVC, not in GitHub. `dvc pull` restores them.")
        with st.expander("➕ Add another month"):
            st.caption("Any SEC BDC data set works, from the SEC page above. Added files are saved only "
                       "on this computer, in data/uploads, with their fingerprint. They go to the S3 bucket "
                       "only when you run: dvc add data/uploads, commit data/uploads.dvc, then dvc push.")
            up_tab, sec_tab, rm_tab = st.tabs(["Upload a ZIP", "Download from the SEC", "Remove an added month"])
            with up_tab:
                files = st.file_uploader("SEC BDC ZIP files (one or several)", type=["zip"],
                                         accept_multiple_files=True)
                names = []
                for f in files or []:
                    m = RELEASE_RE.search(f.name)
                    names.append(st.text_input(f"Month name for {f.name}", value=m.group(0) if m else "",
                                               placeholder="2026_08", key=f"up_name_{f.name}",
                                               help="Like 2026_08 for a month or 2025q4 for a quarter."))
                if files and st.button(f"Add {len(files)} file{'s' if len(files) > 1 else ''}"):
                    added, failed = [], []
                    with st.spinner("Checking and unpacking"):
                        for f, name in zip(files, names):
                            try:
                                r = requests.post(f"{API}/releases/upload", data={"release": name},
                                                  files={"file": (f.name, f.getvalue(), "application/zip")},
                                                  timeout=TIMEOUT)
                            except requests.ConnectionError:
                                failed.append(f"{f.name}: backend not reachable")
                                continue
                            if r.status_code < 400:
                                added.append(r.json()["release"])
                            else:
                                try:
                                    why = r.json().get("detail", r.text)
                                except ValueError:
                                    why = r.text[:300]
                                failed.append(f"{f.name}: {why}")
                    for msg in failed:
                        st.error(msg)
                    if added:
                        ss.add_rel = added
                        if not failed:
                            st.rerun()
            with sec_tab:
                name2 = st.text_input("Month to download", placeholder="2026_08", key="sec_name",
                                      help="Fetched from the SEC page with our name and email, as the SEC requires.")
                if st.button("Download and add", disabled=not name2):
                    with st.spinner(f"Downloading {name2} from the SEC"):
                        e = call("POST", "/releases/fetch", json={"release": name2})
                    ss.add_rel = [e["release"]]
                    st.rerun()
            with rm_tab:
                added = [r["release"] for r in rel_info if r["removable"]]
                if not added:
                    st.caption("No added months yet.")
                else:
                    gone = st.selectbox("Added month", added)
                    if st.button("Remove it"):
                        call("DELETE", f"/releases/{gone}")
                        ss.drop_rel = gone
                        st.rerun()
        st.button("Read these files →", type="primary", on_click=run_then, args=(2,))
    st.stop()
done_row(1, f"{len(run['settings']['releases'])} monthly SEC files "
            f"({', '.join(run['settings']['releases'])}), fingerprints checked")

# ---------------------------------------------------------------- ② read
rd = run["stats"]["read"]
if ss.step == 2:
    with st.container(border=True):
        st.subheader("② What we read from the files")
        funnel = pd.DataFrame({
            "stage": ["Lines in the files", "Only the 31 March 2026 list", "Split lines joined into loans"],
            "count": [rd["soi_rows"], rd["current_rows"], rd["current_holdings"]],
            "why": ["Every line of every report in the chosen months.",
                    "Each report also repeats last December's list. We drop it, or we would count it twice.",
                    "One loan can be spread over several lines. We join them into one loan."]})
        st.altair_chart(alt.Chart(funnel).mark_bar(color="#3b82f6").encode(
            x=alt.X("count:Q", title=None), y=alt.Y("stage:N", sort=None, title=None),
            tooltip=["stage", alt.Tooltip("count:Q", format=","), "why"])
            + alt.Chart(funnel).mark_text(align="left", dx=4, color="white").encode(
            x="count:Q", y=alt.Y("stage:N", sort=None), text=alt.Text("count:Q", format=",")),
            use_container_width=True)
        st.markdown(f"From **{rd['reports']:,} reports** we get **{rd['current_holdings']:,} loans**. "
                    f"Hover a bar to see why it shrinks.")
        pm = pd.DataFrame(rd["per_month"])
        empty = pm.loc[pm["soi_rows"].eq(0), "release"].tolist() if not pm.empty else []
        if empty:
            st.info(f"{', '.join(empty)}: no fund reports with loan lists in this file. Most funds file "
                    f"their 31 March report by mid-May, so later months hold only late filers.")
        with st.expander("Show details"):
            st.dataframe(pm.rename(columns={"release": "Month", "reports": "Reports", "soi_rows": "Lines"}),
                         hide_index=True, use_container_width=True)
            st.caption(f"Read from: {rd['origin']}.")
        st.button("Next: clean the list →", type="primary", on_click=go_to, args=(3,))
    st.stop()
done_row(2, f"{rd['soi_rows']:,} lines → {rd['current_holdings']:,} loans")

# ---------------------------------------------------------------- ③ clean
cl = run["stats"]["clean"]
if ss.step == 3:
    with st.container(border=True):
        st.subheader("③ Remove lines that are not loans")
        st.markdown("Some lines look like loans but are not. Switch the rules on or off and press "
                    "**Apply** to see what each one removes.")
        for r in ALL_RULES:
            st.toggle(f"**{nice(r)}**: {RULE_TEXT.get(r, '')}", key=f"rule_{r}")
        applied = run["settings"]["rules"] == chosen_rules() and run["settings"]["releases"] == sorted(ss.rels)
        if not applied:
            st.button("Apply cleaning", type="primary", on_click=run_then, args=(3,))
        else:
            bcl = ss.baseline["stats"]["clean"]
            a, b, c = st.columns(3)
            a.metric("Loans before", f"{cl['current_holdings']:,}")
            b.metric("Removed", f"{cl['removed']:,}", delta=delta(cl["removed"], bcl["removed"]),
                     delta_color="off")
            c.metric("Loans after", f"{cl['kept']:,}", delta=delta(cl["kept"], bcl["kept"]))
            if run["cleaning_log"]:
                log = pd.DataFrame(run["cleaning_log"])
                log["Rule"] = log["rule"].map(nice)
                st.altair_chart(alt.Chart(log).mark_bar(color="#f59e0b").encode(
                    x=alt.X("rows_affected:Q", title="Lines removed"),
                    y=alt.Y("Rule:N", sort=None, title=None),
                    tooltip=["Rule", "artifact", "rows_affected", "example"]), use_container_width=True)
                with st.expander("Show an example line for each rule"):
                    ex = pd.DataFrame({
                        "Rule": log["Rule"], "Lines removed": log["rows_affected"],
                        "A line it removed": log.get("example_line"),
                        "Its value ($M)": (pd.to_numeric(log.get("example_value"), errors="coerce") / 1e6).round(2),
                        "Where (report / month / SEC row)": log["example"]})
                    st.dataframe(ex, hide_index=True, use_container_width=True)
                    st.caption("Each line is a real line from the SEC file. The last column says where "
                               "to find it.")
            else:
                st.warning("All rules are off: every line counts as a loan. See what that does in the next step.")
            st.button("Next: compare with each fund's total →", type="primary", on_click=go_to, args=(4,))
    st.stop()
done_row(3, f"{len(run['settings']['rules'])} of {len(ALL_RULES)} rules on · {cl['removed']:,} lines removed "
            f"→ {cl['kept']:,} loans")

# ---------------------------------------------------------------- ④ compare
cov, bcov = run["coverage"], ss.baseline["coverage"]
fil, bfil = ss.fil, ss.base_fil
tol = run["settings"]["tolerance"]
if ss.step == 4:
    with st.container(border=True):
        st.subheader("④ Does each report add up?")
        st.markdown("For each report we add up our loans and compare with the total the fund wrote "
                    "itself. Choose how close is close enough:")
        st.slider("Tolerance (%)", 0.1, 5.0, step=0.1, key="tol")
        t = ss.tol / 100
        st.caption(f"Example: a fund total of \\$1,000M passes if our sum is between "
                   f"\\${1000 * (1 - t):,.0f}M and \\${1000 * (1 + t):,.0f}M.")
        if abs(t - tol) > 1e-9 or run["settings"]["rules"] != chosen_rules():
            st.button("Compare", type="primary", on_click=run_then, args=(4,))
        else:
            a, b = st.columns(2)
            a.metric("Reports that pass", f"{cov['filings_admitted']} of {cov['filings_attempted']}",
                     delta=delta(cov["filings_admitted"], bcov["filings_admitted"]))
            b.metric("Share of all dollars covered", f"{cov['share_of_dollars']:.1%}",
                     delta=delta(cov["share_of_dollars"], bcov["share_of_dollars"], "{:+.1%}"),
                     help="The funds' own totals of the passing reports (" + esc(money(cov["filed_fv_admitted"]))
                          + ") ÷ the funds' own totals of all reports (" + esc(money(cov["filed_fv_attempted"])) + ").")
            g = fil.dropna(subset=["gap_pct"]).copy()
            if not g.empty:
                lim = 10.0
                g["gap"] = (g["gap_pct"] * 100).clip(-lim, lim)
                g["result"] = g["admitted"].map({True: "passes", False: "fails"})
                bars = alt.Chart(g).mark_bar().encode(
                    x=alt.X("gap:Q", bin=alt.Bin(step=0.5, extent=[-lim, lim]),
                            title="How far our sum is from the fund's total (%)",
                            axis=alt.Axis(labelExpr="datum.value >= 10 ? '+10 or more' : "
                                                    "(datum.value <= -10 ? '-10 or less' : datum.label)")),
                    y=alt.Y("count()", title="Reports"),
                    color=alt.Color("result:N", title=None, scale=alt.Scale(
                        domain=["passes", "fails"], range=["#2e9e5b", "#d9534f"])))
                band = alt.Chart(pd.DataFrame({"x": [-tol * 100, tol * 100]})).mark_rule(
                    strokeDash=[5, 4], color="#aaa").encode(x="x:Q")
                st.altair_chart(bars + band, use_container_width=True)
                st.caption("Green reports sit between the dashed tolerance lines. The bars at the far "
                           "left and right also hold every report beyond -10% or +10%.")
            if not is_default:
                both = fil[["adsh", "name", "form", "admitted"]].merge(
                    bfil[["adsh", "admitted"]], on="adsh", how="outer", suffixes=("", "_default"))
                up = both[both["admitted"].eq(True) & both["admitted_default"].ne(True)]
                down = both[both["admitted"].ne(True) & both["admitted_default"].eq(True)]
                with st.expander(f"Compared with the team default: {len(up)} now pass, {len(down)} now fail"):
                    l, r = st.columns(2)
                    l.dataframe(up[["name", "form"]], hide_index=True, use_container_width=True)
                    r.dataframe(down[["name", "form"]], hide_index=True, use_container_width=True)
            st.markdown("**Which reports add up, and why the others do not**")
            report_status(fil, "walk")
            st.button("Next: the final list →", type="primary", on_click=go_to, args=(5,))
    st.stop()
done_row(4, f"tolerance {tol:.1%} · {cov['filings_admitted']} of {cov['filings_attempted']} reports pass "
            f"· {cov['share_of_dollars']:.1%} of dollars")

# ---------------------------------------------------------------- ⑤ final list
fn = run["stats"]["final"]
if ss.step == 5:
    with st.container(border=True):
        st.subheader("⑤ The final list")
        st.markdown(f"Only the loans of the **{fn['reports']} reports that passed** go in: "
                    f"**{fn['loans']:,} loans**. Pick any fund to look inside its report.")
        names = fil.sort_values("name")
        labels = {r.adsh: f"{'✅' if r.admitted else '❌'} {r.name} ({r.form})" for r in names.itertuples()}
        pick = st.selectbox("Fund report", list(labels), format_func=labels.get, index=None,
                            placeholder="Type a fund name, for example Ares or Golub")
        if pick:
            d = call("GET", f"/runs/{run['run_id']}/filings/{pick}/holdings")
            f = d["filing"]
            a, b, c = st.columns(3)
            a.metric("Our sum of its loans", money(f["holdings_fv"]))
            b.metric("Total the fund reported", money(f["filed_fv"]))
            c.metric("Gap", "n/a" if f["gap_pct"] is None else f"{f['gap_pct']:+.2%}")
            if f["gap_pct"] is None:
                st.warning("No usable total or no loans, so there is nothing to compare.")
            elif f["admitted"]:
                st.success(f"Inside the {tol:.1%} tolerance: its {f['n_holdings']:,} loans are in the final list.")
            else:
                st.error(f"Outside the {tol:.1%} tolerance, so it is left out. Reason: {f['triage_category']}.")
            if f.get("filing_url"):
                st.link_button("Open the original report on SEC.gov ↗", f["filing_url"])
            h = pd.DataFrame(d["holdings"])
            if not h.empty:
                with st.expander(f"Show its {len(h):,} loans (largest first)"):
                    st.caption("source_rows = row numbers in that month's SEC file, so each loan traces back.")
                    st.dataframe(h.drop(columns=["filing_url"], errors="ignore"),
                                 hide_index=True, use_container_width=True)
        with st.expander("Download this run"):
            st.download_button("⬇ Reports (CSV)", fil.to_csv(index=False),
                               file_name=f"lantern_reports_{run['run_id']}.csv", mime="text/csv")
            if st.button("Prepare loans (CSV)"):
                ss[f"panel_{run['run_id']}"] = call("GET", f"/runs/{run['run_id']}/panel.csv", raw=True)
            if f"panel_{run['run_id']}" in ss:
                st.download_button("⬇ Loans (CSV)", ss[f"panel_{run['run_id']}"],
                                   file_name=f"lantern_loans_{run['run_id']}.csv", mime="text/csv")
        st.button("Next: check some loans by hand →", type="primary", on_click=go_to, args=(6,))
    st.stop()
done_row(5, f"{fn['loans']:,} loans from {fn['reports']} reports")

# ---------------------------------------------------------------- ⑥ check by hand
with st.container(border=True):
    st.subheader("⑥ Are single loans right too?")
    st.markdown("A matching total can still hide wrong lines. So we opened the real reports and "
                "checked single loans by hand.")
    rv = pd.DataFrame(get("/spot-checks"))
    if rv.empty:
        st.info("No hand checks found in reports/spot_check.csv.")
    else:
        done = rv[rv["matches"].ne("")]
        yes = int((done["matches"] == "yes").sum())
        st.metric("Loans that match the fund's report", f"{yes} of {len(done)}")
        for m in done[done["matches"] != "yes"].itertuples():
            st.warning(f"Row {m.Index + 1}, {pretty(m.name)}: {m.note}")
        n = lambda c: (pd.to_numeric(rv[c], errors="coerce") / 1e6).map(  # noqa: E731
            lambda x: "" if pd.isna(x) else f"{x:,.2f}")
        num = list(range(1, len(rv) + 1))
        left, right = st.columns(2)
        left.markdown("**What our list says** (from the pipeline)")
        left.dataframe(pd.DataFrame({
            "#": num, "Fund": rv["name"].map(pretty), "Loan": rv["identifier"],
            "Value ($M)": n("fair_value"), "Owed ($M)": n("principal"), "SEC rows": rv["source_rows"]}),
            hide_index=True, use_container_width=True, height=460)
        right.markdown("**What the report says** (checked by hand)")
        right.dataframe(pd.DataFrame({
            "#": num, "Value ($M)": n("filing_fair_value"), "Owed ($M)": n("filing_principal"),
            "Match": rv["matches"].map({"yes": "✅ yes", "no": "❌ no"}).fillna(""),
            "Note": rv["note"], "Report": rv["filing_url"]}),
            hide_index=True, use_container_width=True, height=460,
            column_config={"Report": st.column_config.LinkColumn("Report", display_text="open ↗")})
        st.caption("Same row number = same loan. Values are in $ millions.")
    with st.expander("Draw your own sample to check"):
        st.caption("Picks the largest passing reports plus some at random, then loans from each. "
                   "The same seed always gives the same sample.")
        s1, s2, s3, s4 = st.columns(4)
        n_largest = s1.number_input("Largest reports", 0, 50, 5)
        n_random = s2.number_input("Random reports", 0, 50, 5)
        per_filing = s3.number_input("Loans per report", 1, 10, 2)
        seed = s4.number_input("Seed", 0, 10_000, 7)
        if st.button("Draw sample"):
            smp = pd.DataFrame(call("POST", f"/runs/{run['run_id']}/sample", json={
                "n_largest": int(n_largest), "n_random": int(n_random),
                "per_filing": int(per_filing), "seed": int(seed)}))
            if smp.empty:
                st.info("No passing reports in this run.")
            else:
                st.dataframe(smp, hide_index=True, use_container_width=True,
                             column_config={"filing_url": st.column_config.LinkColumn("report", display_text="open")})
    st.success("That's the whole pipeline. Change any step above, or try a quick experiment in the sidebar.")
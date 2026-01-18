from typing import Final

SIGNATURES: Final[list[str]] = ["ciphers", "alpn", "curves", "sig_algs"]


def apply_ja3_overrides(profile: dict, ja3: dict | None) -> dict:
    """
    Apply JA3-like overrides onto a profile.

    Supported keys in ja3 dict:
      - ciphers: list[str] or OpenSSL cipher string
      - alpn: list[str]
      - curves: list[str]
      - sig_algs: list[str]
    """
    if not ja3:
        return profile
    tls = profile.setdefault("tls", {})
    for key in SIGNATURES:
        if key in ja3 and ja3[key]:
            tls[key] = ja3[key]
    # Mirror ALPN into http2 profile if provided.
    if "alpn" in ja3 and ja3["alpn"]:
        h2 = profile.setdefault("http2", {})
        if isinstance(ja3["alpn"], (list, tuple)):
            h2["alpn"] = list(ja3["alpn"])
    return profile


def apply_tls_configuration_options(profile: dict, tls_opts: dict | None) -> dict:
    """
    Accepts curl_cffi-style tls_configuration_options and stores them on the
    profile for future native ClientHello work. Currently, ja3_str/akamai_str
    are preserved; extra_fp (ExtraFingerprints) is attached. We also mirror
    provided ALPN lists into profile where possible.
    """
    if not tls_opts:
        return profile
    if "ja3_str" in tls_opts:
        profile["ja3_str"] = tls_opts["ja3_str"]
    if "akamai_str" in tls_opts:
        profile["akamai_str"] = tls_opts["akamai_str"]
    extra_fp = tls_opts.get("extra_fp")
    if extra_fp:
        profile["extra_fp"] = extra_fp
        if getattr(extra_fp, "alpn", None):
            profile.setdefault("tls", {})["alpn"] = list(extra_fp.alpn)
            profile.setdefault("http2", {})["alpn"] = list(extra_fp.alpn)
        if getattr(extra_fp, "ciphers", None):
            profile.setdefault("tls", {})["ciphers"] = ":".join(extra_fp.ciphers)
        if getattr(extra_fp, "curves", None):
            profile.setdefault("tls", {})["curves"] = list(extra_fp.curves)
        if getattr(extra_fp, "sig_algs", None):
            profile.setdefault("tls", {})["sig_algs"] = list(extra_fp.sig_algs)
    return profile

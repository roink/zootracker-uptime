import sqlite3

from latin_name_parser import parse_latin_name
from normalize_latin_names import update_animals
from zootier_scraper_sqlite import ensure_db_schema

def test_simple_synonyms():
    name = "Abantennarius coccineus(Syn.: Antennatus coccineus)(Syn.: Antennarius coccineus)"
    parsed = parse_latin_name(name)
    assert parsed.normalized == "Abantennarius coccineus"
    assert parsed.alternative_names == [
        "Antennatus coccineus",
        "Antennarius coccineus",
    ]


def test_abbreviated_synonyms():
    name = "Amazona farinosa farinosa(Syn.: A. f. chapmani)(Syn.: A. f. inornata)"
    parsed = parse_latin_name(name)
    assert parsed.normalized == "Amazona farinosa farinosa"
    assert parsed.alternative_names == [
        "Amazona farinosa chapmani",
        "Amazona farinosa inornata",
    ]


def test_parenthetical_qualifier():
    name = "Hymenochirus(cf.) boettgeri"
    parsed = parse_latin_name(name)
    assert parsed.normalized == "Hymenochirus boettgeri"
    assert parsed.qualifier == "cf"
    assert parsed.qualifier_target == "boettgeri"


def test_trade_code_and_locality(tmp_path):
    name = "Panaque cf. armbrusteri(L 27 Rio Araguaia)"
    parsed = parse_latin_name(name)
    assert parsed.normalized == "Panaque armbrusteri"
    assert parsed.qualifier == "cf"
    assert parsed.qualifier_target == "armbrusteri"
    assert parsed.trade_code == "L27"
    assert parsed.locality == "Rio Araguaia"

    db = tmp_path / "db.sqlite"
    conn = sqlite3.connect(db)
    ensure_db_schema(conn)
    c = conn.cursor()
    c.execute(
        "INSERT INTO animal (art, klasse, ordnung, familie, latin_name) VALUES (?,?,?,?,?)",
        ("1", 1, 1, 1, name),
    )
    update_animals(conn)
    row = c.execute(
        "SELECT normalized_latin_name, alternative_latin_names, qualifier, qualifier_target, locality, trade_code FROM animal WHERE art=?",
        ("1",),
    ).fetchone()
    assert row == (
        "Panaque armbrusteri",
        "[]",
        "cf",
        "armbrusteri",
        "Rio Araguaia",
        "L27",
    )
    conn.close()


def test_chained_abbreviated_synonyms():
    name = (
        "Kinyongia multituberculata"
        "(Syn.: Chamaeleon fischeri multituberculatus)"
        "(Syn.: C. f. werneri)"
    )
    parsed = parse_latin_name(name)
    assert parsed.normalized == "Kinyongia multituberculata"
    assert parsed.alternative_names == [
        "Chamaeleon fischeri multituberculatus",
        "Chamaeleon fischeri werneri",
    ]

def test_aff_and_morph_label_in_quotes():
    parsed = parse_latin_name('Oligosoma aff. infrapunctatum "Cobble"')
    assert parsed.normalized == "Oligosoma infrapunctatum"
    assert parsed.qualifier == "aff"
    assert parsed.qualifier_target == "infrapunctatum"
    assert parsed.locality == "Cobble"

def test_sp_cf_placeholder():
    parsed = parse_latin_name("Andriashevicottus sp. cf. megacephalus")
    assert parsed.normalized == "Andriashevicottus sp."
    assert parsed.qualifier == "cf"
    assert parsed.qualifier_target == "megacephalus"

def test_cf_simple():
    parsed = parse_latin_name("Hyphessobrycon cf. pulchripinnis")
    assert parsed.normalized == "Hyphessobrycon pulchripinnis"
    assert parsed.qualifier == "cf"
    assert parsed.qualifier_target == "pulchripinnis"

def test_aff_simple():
    parsed = parse_latin_name("Chitala aff. lopis")
    assert parsed.normalized == "Chitala lopis"
    assert parsed.qualifier == "aff"
    assert parsed.qualifier_target == "lopis"

def test_synonym_with_includes_and_abbrev():
    parsed = parse_latin_name(
        "Pterophyllum scalare(Syn.: Pterophyllum eimekei)(Syn.: P. dumerilii)(inkl. P. cf. scalare)"
    )
    assert parsed.normalized == "Pterophyllum scalare"
    assert set(parsed.alternative_names) >= {
        "Pterophyllum eimekei",
        "Pterophyllum dumerilii",
        "Pterophyllum scalare",
    }

def test_trade_code_and_locality_2():
    parsed = parse_latin_name("Panaque cf. armbrusteri(L 27 Rio Tocantins)")
    assert parsed.trade_code == "L27"
    assert parsed.locality == "Rio Tocantins"

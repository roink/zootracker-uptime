from gemini_utils import AnimalRecord, ZooRecord


def test_animal_record_descriptions_are_cleaned():
    record = AnimalRecord(
        description_en="  **Bold**  hunter  ",
        description_de="#Überschrift\nMehr   Text",
    )

    assert record.description_en == "Bold hunter"
    assert record.description_de == "Überschrift Mehr Text"


def test_zoo_record_descriptions_are_cleaned():
    record = ZooRecord(
        description_en="__Playful__  exhibit",
        description_de="*Familien*  #Tag",
    )

    assert record.description_en == "Playful exhibit"
    assert record.description_de == "Familien Tag"

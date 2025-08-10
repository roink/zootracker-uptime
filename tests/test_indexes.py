from sqlalchemy import inspect
from app.database import engine


def test_zooanimal_indexes_present():
    insp = inspect(engine)
    idx = {i['name'] for i in insp.get_indexes('zoo_animals')}
    assert 'idx_zooanimal_animal_id' in idx
    assert 'idx_zooanimal_zoo_id' in idx


def test_zoo_location_index_present():
    insp = inspect(engine)
    idx = {i['name'] for i in insp.get_indexes('zoos')}
    assert 'idx_zoos_location_gist' in idx

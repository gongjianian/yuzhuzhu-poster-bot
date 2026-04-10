def test_all_categories_count():
    from symptom_categories import ALL_SYMPTOM_CATEGORIES, LEVEL1_CATEGORIES
    assert len(ALL_SYMPTOM_CATEGORIES) == 10
    assert len(LEVEL1_CATEGORIES) == 3

def test_category_fields():
    from symptom_categories import ALL_SYMPTOM_CATEGORIES
    cat = ALL_SYMPTOM_CATEGORIES[0]
    assert cat["id"]
    assert cat["name"]
    assert cat["level1_id"]
    assert cat["level1_name"]
    assert cat["description"]
    assert cat["symptoms"]

def test_category_ids_unique():
    from symptom_categories import ALL_SYMPTOM_CATEGORIES
    ids = [c["id"] for c in ALL_SYMPTOM_CATEGORIES]
    assert len(ids) == len(set(ids))

def test_get_category_by_id():
    from symptom_categories import get_category_by_id
    cat = get_category_by_id("cat_pw_jstl")
    assert cat["name"] == "积食停滞类"
    assert get_category_by_id("nonexistent") is None

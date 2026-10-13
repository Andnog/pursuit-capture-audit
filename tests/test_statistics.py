import pytest

from pursuit_audit.statistics.bootstrap import family_bootstrap
from pursuit_audit.statistics.contrasts import EpisodeKey, cell_means, paired_differences


def test_no_differences_give_no_interval():
    assert family_bootstrap({}) is None
    assert family_bootstrap({("city", 0, "RANDOM"): []}) is None


def test_identical_differences_give_a_degenerate_interval():
    differences = {("a", i, "RANDOM"): [0.25, 0.25] for i in range(12)}
    interval = family_bootstrap(differences, resamples=200)
    assert interval.as_list() == [0.25, 0.25, 0.25]
    assert interval.excludes_zero()


def test_the_interval_is_reproducible_and_contains_the_estimate():
    differences = {("a", i, "RANDOM"): [(-1) ** i * 0.1 * (i % 5), 0.05] for i in range(40)}
    first = family_bootstrap(differences, resamples=500)
    assert first == family_bootstrap(differences, resamples=500)
    assert first.low <= first.estimate <= first.high


def test_a_higher_level_gives_a_wider_interval():
    differences = {("a", i, "RANDOM"): [0.02 * (i % 7) - 0.03] for i in range(60)}
    narrow = family_bootstrap(differences, resamples=2000, alpha=0.05)
    wide = family_bootstrap(differences, resamples=2000, alpha=0.025)
    assert wide.low <= narrow.low and narrow.high <= wide.high


def test_resampling_cities_first_widens_an_interval_with_city_effects():
    differences = {}
    for city, shift in (("a", 0.0), ("b", 0.1), ("c", 0.3), ("d", -0.1)):
        for i in range(25):
            differences[(city, i, "RANDOM")] = [shift + 0.01 * (i % 3)]
    families = family_bootstrap(differences, resamples=2000)
    cities = family_bootstrap(differences, resamples=2000, two_stage=True)
    assert cities.high - cities.low > families.high - families.low


RECORDS = {
    "T|plb|x|0|9500|RANDOM|3": {"d06": True},
    "T|plb|x|0|9501|RANDOM|3": {"d06": False},
    "T|pursuit|x|0|9500|RANDOM|3": {"d06": False},
    "T|pursuit|x|0|9501|RANDOM|3": {"d06": False},
    "T|plb|x|0|9500|OPTIMAL_ESCAPE|3": {"d06": True},
    "T|pursuit|x|0|9500|OPTIMAL_ESCAPE|3": {"d06": True},
    "T|plb|x|1|9500|RANDOM|3": {"failed": "placement"},
    "N|null|x|0|9500|RANDOM|5": {"d06": False},
}


def test_keys_are_parsed():
    key = EpisodeKey.parse("T|plb|x|0|9500|RANDOM|3")
    assert key.cell == ("x", 0, "RANDOM", 3)


def test_cell_means_average_seeds_and_skip_failures():
    means = cell_means(RECORDS, "d06", "T", "plb")
    assert means == {("x", 0, "RANDOM", 3): 0.5, ("x", 0, "OPTIMAL_ESCAPE", 3): 1.0}


def test_paired_differences_keep_shared_cells_of_the_chosen_evaders():
    plb = cell_means(RECORDS, "d06", "T", "plb")
    pursuit = cell_means(RECORDS, "d06", "T", "pursuit")
    assert paired_differences(plb, pursuit, ("RANDOM",)) == {("x", 0, "RANDOM"): [0.5]}
    assert paired_differences(plb, pursuit, ("RANDOM",), city="y") == {}
    both = paired_differences(plb, pursuit, ("RANDOM", "OPTIMAL_ESCAPE"))
    assert both[("x", 0, "OPTIMAL_ESCAPE")] == [pytest.approx(0.0)]

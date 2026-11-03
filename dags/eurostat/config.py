"""Fixed dataset contracts for the Eurostat portfolio pipeline."""

POSTGRES_CONN_ID = "eurostat_postgres"
DATASETS = {
    "gdp": {
        "code": "nama_10_gdp",
        "table": "eurostat_gdp",
        "params": {
            "format": "JSON",
            "freq": "A",
            "lang": "en",
            "na_item": "B1GQ",  # Gross domestic product
            "unit": "CP_MEUR",  # Current prices, million euro
            "sinceTimePeriod": "2015",
        },
        "geos": ["DE", "FR", "IT", "ES", "NL", "PL", "EU27_2020"],
    },
    "employment": {
        "code": "lfsi_emp_a",
        "table": "eurostat_employment",
        "params": {
            "format": "JSON",
            "freq": "A",
            "lang": "en",
            "sex": "T",
            "age": "Y15-64",
            "indic_em": "EMP_LFS",
            "unit": "PC_POP",  # Percentage of population
            "sinceTimePeriod": "2015",
        },
        "geos": ["DE", "FR", "IT", "ES", "NL", "PL", "EU27_2020"],
    },
}

BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

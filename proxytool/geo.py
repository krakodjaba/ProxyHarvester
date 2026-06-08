import geoip2.database

reader = geoip2.database.Reader("proxytool/GeoLite2-Country.mmdb")

def get_country(ip: str):
    try:
        return reader.country(ip).country.iso_code
    except Exception:
        return "XX"
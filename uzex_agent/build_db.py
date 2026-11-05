"""CSV fayllardan DuckDB bazasini quradi: python -m uzex_agent.build_db <csv_papka> <db_fayl>"""
from __future__ import annotations

import os
import sys

import duckdb
import pandas as pd

from .normalize import PRODUCTS, company_key, contract_attrs, fold, to_latin

REGIONS = {
    "Toshkent shahri": ("г. Ташкент", "Ташкент город Toshkent sh"),
    "Toshkent viloyati": ("Ташкентская область", "Ташкентская обл"),
    "Andijon viloyati": ("Андижанская область", "Андижан Andijon"),
    "Buxoro viloyati": ("Бухарская область", "Бухара Buxoro"),
    "Farg‘ona viloyati": ("Ферганская область", "Фергана Fargona"),
    "Jizzax viloyati": ("Джизакская область", "Джизак Jizzax"),
    "Namangan viloyati": ("Наманганская область", "Наманган Namangan"),
    "Navoiy viloyati": ("Навоийская область", "Навои Navoiy"),
    "Qashqadaryo viloyati": ("Кашкадарьинская область", "Кашкадарья Qashqadaryo"),
    "Qoraqalpog‘iston Respublikasi": ("Республика Каракалпакстан", "Каракалпакстан Qoraqalpogiston"),
    "Samarqand viloyati": ("Самаркандская область", "Самарканд Samarqand"),
    "Sirdaryo viloyati": ("Сырдарьинская область", "Сырдарья Sirdaryo"),
    "Surxondaryo viloyati": ("Сурхандарьинская область", "Сурхандарья Surxondaryo"),
    "Xorazm viloyati": ("Хорезмская область", "Хорезм Xorazm"),
}

NUM = "try_cast(replace(replace({c}, ' ', ''), chr(160), '') as DOUBLE)"


def build(src: str, db_path: str) -> None:
    tmp = db_path + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    con = duckdb.connect(tmp)
    rd = lambda f: f"read_csv('{os.path.join(src, f)}', header=true, all_varchar=true)"

    # --- ishtirokchilar va brokerlar ---
    p = con.execute(f"select * from {rd('participants.csv')}").df()
    p.columns = ["inn", "name", "region", "activity", "role", "vat_payer"]
    p["name_latin"] = p["name"].map(to_latin)
    p["name_key"] = p["name"].map(company_key)
    p["vat_payer"] = p["vat_payer"].eq("Да")

    b = con.execute(f"select * from {rd('brokers.csv')}").df()
    b.columns = ["code", "name", "inn", "region"]
    b["name_latin"] = b["name"].map(to_latin)
    b["name_key"] = b["name"].map(company_key)

    # --- shartnomalar ---
    k = con.execute(f"select * from {rd('contracts.csv')}").df()
    attrs = pd.DataFrame(
        [
            contract_attrs(r["Наименование продукта"], r["Марка товара"], r["Размер товара"],
                           r["Сорт товара"], r["Тип товара"], r["Класс товара"])
            for r in k.to_dict("records")
        ]
    )
    k = pd.concat([k, attrs], axis=1)
    con.register("k_df", k)
    con.register("p_df", p)
    con.register("b_df", b)

    con.execute("create table participants as select inn,name,name_latin,region,activity,role,vat_payer,name_key from p_df")
    con.execute("create table brokers as select code,name,name_latin,inn,region,name_key from b_df")
    con.execute(
        f"""create table usd_rates as select strptime("Дата",'%d.%m.%Y')::DATE rate_date, "Курс"::DOUBLE rate
            from {rd('usd_rates.csv')} order by 1"""
    )
    reg = pd.DataFrame([(u, r, s) for u, (r, s) in REGIONS.items()], columns=["region", "region_ru", "aliases"])
    con.register("reg_df", reg)
    con.execute("create table regions as select * from reg_df")

    con.execute(
        f"""
        create table contracts as
        select "Номер контракта"::BIGINT contract_id, "Наименование продукта" product_raw, k.product, k.product_uz,
               k.grade, k."class", k.brand, k.size, k.kind,
               "Код ТН ВЭД" hs_code, "Группа товара" product_group, "Категория товара" category,
               "Отрасль промышленности" industry, "Единица измерения" unit, "Лот"::DOUBLE lot_size,
               case when "Валюта"='Доллар США' then 'USD' else 'UZS' end currency,
               "Базисная цена"::DOUBLE base_price,
               try_cast(replace("Сумма залога",' %','') as DOUBLE) deposit_pct,
               "Базис поставки" delivery_basis, "Упаковка" packaging,
               r.region, k."Регион" region_ru, "Адрес склада" warehouse_address,
               "Тип торгов" auction_type, "Тип контракта" contract_type, "Форма контракта" contract_form,
               "Срок оплаты"::INT payment_term_days, "Срок поставки"::INT delivery_term_days,
               "ИНН продавца" seller_inn, s.name seller_name,
               strptime("Дата регистрации",'%d.%m.%Y')::DATE registered_on,
               strptime("Действует до",'%d.%m.%Y')::DATE valid_until
        from k_df k
        left join reg_df r on r.region_ru=k."Регион"
        left join p_df s on s.inn=k."ИНН продавца"
        """
    )

    # --- bitimlar: bitta keng jadval ---
    con.execute(
        f"""
        create table deals as
        with d as (
            select "Номер сделки"::BIGINT deal_id,
                   strptime("Дата сделки",'%d.%m.%Y')::DATE deal_date,
                   "Время сделки" deal_time, "Тип торгов" auction_type,
                   {NUM.format(c='"Количество"')} lots,
                   {NUM.format(c='"Сумма сделки"')} amount,
                   {NUM.format(c='"Стартовая цена"')} start_price,
                   "Номер контракта"::BIGINT contract_id,
                   "Наименование товара" product_raw,
                   "Лот"::DOUBLE lot_size, "Единица измерения" unit,
                   "Регион" region, "Тип контракта" contract_type, "Форма контракта" contract_form,
                   "Состояние сделки" status,
                   "ИНН продавца" seller_inn, "ИНН покупателя" buyer_inn,
                   "Брокер продавца" seller_broker, "Брокер покупателя" buyer_broker,
                   try_strptime("Дата оплаты",'%d.%m.%Y')::DATE payment_date,
                   try_strptime("Дата поставки",'%d.%m.%Y')::DATE delivery_date,
                   {NUM.format(c='"Поставлено"')} delivered_lots
            from read_csv('{os.path.join(src, 'deals_*.csv')}', header=true, all_varchar=true)
        )
        select d.*,
               year(deal_date) deal_year, strftime(deal_date,'%Y-%m') deal_month,
               c.currency, c.product, c.product_uz, c.grade, c."class", c.brand, c.size, c.kind,
               c.hs_code, c.category, c.product_group, c.industry,
               r.region_ru,
               lots*d.lot_size volume,
               delivered_lots*d.lot_size delivered_volume,
               amount/(lots*d.lot_size) unit_price,
               case d.unit when 'тонна' then lots*d.lot_size
                           when 'килограмм' then lots*d.lot_size/1000 end mass_tons,
               u.rate usd_rate,
               case when c.currency='USD' then amount*u.rate else amount end amount_uzs,
               case when c.currency='USD' then amount else amount/u.rate end amount_usd,
               status='Аннулирован(Не оплачен)' is_cancelled,
               s.name seller_name, s.name_latin seller_name_latin, s.region seller_region,
               bu.name buyer_name, bu.name_latin buyer_name_latin, bu.region buyer_region,
               sb.name seller_broker_name, bb.name buyer_broker_name,
               c.payment_term_days, c.delivery_term_days,
               date_diff('day',deal_date,payment_date) days_to_payment,
               date_diff('day',payment_date,delivery_date) days_to_delivery,
               greatest(date_diff('day',payment_date,delivery_date)-c.delivery_term_days,0) delivery_late_days
        from d
        join contracts c using(contract_id)
        left join regions r on r.region=d.region
        left join usd_rates u on u.rate_date=d.deal_date
        left join participants s on s.inn=d.seller_inn
        left join participants bu on bu.inn=d.buyer_inn
        left join brokers sb on sb.code=d.seller_broker
        left join brokers bb on bb.code=d.buyer_broker
        order by deal_id
        """
    )

    prod = [(ru, uz, syn) for _, ru, uz, syn in PRODUCTS]
    pdf = pd.DataFrame(prod, columns=["product", "product_uz", "aliases"]).drop_duplicates("product")
    con.register("pdf", pdf)
    con.execute(
        """create table products as
           select p.product,p.product_uz,p.aliases,x.category,x.units,x.deal_count
           from pdf p join (select product,min(category) category,list(distinct unit) units,count(*) deal_count
                            from deals group by 1) x using(product)"""
    )
    con.execute("drop view if exists k_df; ")
    con.close()
    os.replace(tmp, db_path)


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
    print("OK", sys.argv[2], os.path.getsize(sys.argv[2]) // 1024 // 1024, "MB")

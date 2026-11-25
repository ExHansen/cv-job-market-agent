select
    company_key,
    trim(company_name) as company_name,
    coalesce(industry, 'Technology') as industry,
    coalesce(company_stage, '') as company_stage,
    coalesce(headquarters, 'Indonesia') as headquarters,
    overall_rating,
    work_life_balance,
    culture_score,
    career_growth,
    verdict,
    salary_idr_junior,
    salary_idr_mid,
    salary_idr_senior,
    updated_at
from {{ source('bronze_raw', 'company_profiles') }}
where company_key is not null

with open_jobs as (
    select
        lower(trim(company_name)) as company_norm,
        company_name,
        count(distinct job_id) as open_roles_count,
        sum(case when work_mode = 'Remote' then 1 else 0 end) as remote_roles_count,
        max(scraped_at) as last_seen_at
    from {{ ref('stg_job_postings') }}
    group by lower(trim(company_name)), company_name
)

select
    coalesce(cp.company_name, oj.company_name) as company_name,
    coalesce(cp.industry, 'Technology') as industry,
    coalesce(cp.verdict, 'Unrated') as verdict,
    cp.overall_rating,
    cp.work_life_balance,
    cp.salary_idr_junior,
    cp.salary_idr_mid,
    coalesce(oj.open_roles_count, 0) as open_roles_count,
    coalesce(oj.remote_roles_count, 0) as remote_roles_count,
    oj.last_seen_at
from {{ ref('stg_company_profiles') }} cp
full outer join open_jobs oj
    on lower(cp.company_name) = oj.company_norm
order by open_roles_count desc, cp.overall_rating desc nulls last

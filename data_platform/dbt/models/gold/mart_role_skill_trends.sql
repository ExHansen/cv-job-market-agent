with role_totals as (
    select
        role_family,
        count(distinct job_id) as total_jobs_in_role
    from {{ ref('stg_job_postings') }}
    group by role_family
),

skill_counts as (
    select
        p.role_family,
        s.skill_canonical,
        s.skill_category,
        count(distinct p.job_id) as job_count
    from {{ ref('stg_job_postings') }} p
    inner join {{ ref('stg_job_skills') }} s
        on p.job_id = s.job_id
    group by p.role_family, s.skill_canonical, s.skill_category
)

select
    sc.role_family || '::' || sc.skill_canonical as role_skill_id,
    sc.role_family,
    sc.skill_canonical,
    sc.skill_category,
    sc.job_count,
    rt.total_jobs_in_role,
    round(sc.job_count * 100.0 / nullif(rt.total_jobs_in_role, 0), 1) as demand_pct,
    case
        when (sc.job_count * 100.0 / nullif(rt.total_jobs_in_role, 0)) >= 40.0 then 'Mandatory'
        when (sc.job_count * 100.0 / nullif(rt.total_jobs_in_role, 0)) >= 15.0 then 'Rising'
        else 'Niche'
    end as skill_tier
from skill_counts sc
inner join role_totals rt
    on sc.role_family = rt.role_family
order by sc.role_family, demand_pct desc

with postings as (
    select * from {{ ref('stg_job_postings') }}
),

skills_per_job as (
    select
        job_id,
        count(distinct skill_canonical) as extracted_skill_count
    from {{ ref('stg_job_skills') }}
    group by job_id
)

select
    cast(p.scraped_at as date) as ingestion_date,
    p.source,
    count(distinct p.job_id) as jobs_ingested,
    sum(case when p.work_mode = 'Remote' then 1 else 0 end) as remote_jobs,
    sum(case when p.description_length >= 100 then 1 else 0 end) as jobs_with_rich_jd,
    round(
        avg(coalesce(spj.extracted_skill_count, 0)),
        2
    ) as avg_skills_per_job
from postings p
left join skills_per_job spj
    on p.job_id = spj.job_id
group by cast(p.scraped_at as date), p.source
order by ingestion_date desc, jobs_ingested desc

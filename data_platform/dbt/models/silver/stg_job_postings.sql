with raw as (
    select
        job_id,
        coalesce(nullif(trim(source), ''), 'unknown') as source,
        trim(search_role) as search_role,
        trim(title) as job_title,
        coalesce(nullif(trim(company), ''), 'Unknown') as company_name,
        coalesce(trim(location), '') as location,
        coalesce(trim(job_url), '') as job_url,
        coalesce(description, '') as description,
        try_cast(left(cast(posted_at as varchar), 10) as date) as posted_date,
        cast(scraped_at as timestamp) as scraped_at
    from {{ source('bronze_raw', 'job_postings') }}
    where job_id is not null
),

deduped as (
    select
        *,
        row_number() over (partition by job_id order by scraped_at desc) as rn
    from raw
)

select
    job_id,
    source,
    search_role,
    job_title,
    company_name,
    location,
    job_url,
    description,
    length(description) as description_length,
    posted_date,
    scraped_at,
    case
        when source in ('remotive', 'remoteok')
            or lower(job_title || ' ' || location || ' ' || left(description, 400)) like '%remote%'
            then 'Remote'
        when lower(job_title || ' ' || location) like '%hybrid%'
            then 'Hybrid'
        else 'On-site'
    end as work_mode,
    case
        when lower(job_title) like '%quality%' or lower(job_title) like '%dqc%'
            then 'Data Quality'
        when lower(job_title) like '%analytics engineer%'
            then 'Analytics Engineer'
        when lower(job_title) like '%data engineer%' or lower(job_title) like '%etl%'
            then 'Data Engineer'
        when lower(job_title) like '%analyst%' or lower(job_title) like '%bi %'
            then 'Data Analyst'
        when lower(job_title) like '%ai %' or lower(job_title) like '%machine learning%' or lower(job_title) like '%llm%'
            then 'AI / ML'
        else 'Other Data'
    end as role_family,
    case
        when lower(location) like '%indonesia%'
            or lower(location) like '%jakarta%'
            or lower(location) like '%bandung%'
            or lower(location) like '%surabaya%'
            then true
        else false
    end as is_indonesia
from deduped
where rn = 1

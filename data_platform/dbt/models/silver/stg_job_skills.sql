select distinct
    s.job_id,
    trim(s.skill_canonical) as skill_canonical,
    coalesce(nullif(trim(s.category), ''), 'general') as skill_category
from {{ source('bronze_raw', 'job_skills') }} s
inner join {{ ref('stg_job_postings') }} p
    on s.job_id = p.job_id
where s.skill_canonical is not null
  and trim(s.skill_canonical) <> ''

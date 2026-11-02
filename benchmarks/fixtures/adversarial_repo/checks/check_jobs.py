from app.api.jobs import job_retry_schedule

assert job_retry_schedule(1, 0) == []
assert job_retry_schedule(1, 4) == [1, 2, 4, 8]
assert job_retry_schedule(0.5, 3) == [0.5, 1.0, 2.0]
print("job checks passed")

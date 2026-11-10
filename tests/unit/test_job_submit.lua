local source = arg[1]
local resources = arg[2]

slurm = {
	SUCCESS = 0,
	ERROR = 1,
	user_msg = function(message) end,
}

local function check(condition, message)
	if not condition then
		error(message)
	end
end

local prefix = "_SLURM_SPANK_OPTION_spank_quantum_"
local function environment(overrides)
	local values = {
		qpu = "nwqsim",
		workload_kind = "quantum",
		circ_count = "2",
		max_qubits = "5",
		max_depth = "120",
		max_shots = "1024",
	}
	for key, value in pairs(overrides or {}) do
		values[key] = value
	end
	local output = {}
	for key, value in pairs(values) do
		if value ~= false then
			table.insert(output, prefix .. key .. "=" .. value)
		end
	end
	return output
end

local original_getenv = os.getenv
os.getenv = function(name)
	if name == "QFW_SLURM_RESOURCES_FILE" then
		return resources
	end
	if name == "QFW_SLURM_LUA_TEST" then
		return "1"
	end
	return original_getenv(name)
end
local module = dofile(source)
os.getenv = original_getenv

local output, err = module.directive({
	spank_job_env = environment(),
	partition = "quantum",
})
check(err == nil, err)
check(output == "#QFW v=1 qpu=nwqsim-site workload=quantum " ..
	"circuits=2 qubits=5 depth=120 shots=1024", output)

output, err = module.directive({spank_job_env = nil})
check(output == "" and err == nil, "ordinary jobs must be unchanged")

output, err = module.directive({
	spank_job_env = environment({max_shots = false}),
	partition = "quantum",
})
check(output == nil and string.find(err, "max%-shots"),
	"missing fields must fail")

output, err = module.directive({
	spank_job_env = environment({max_shots = "1x"}),
	partition = "quantum",
})
check(output == nil and string.find(err, "numeric"),
	"malformed numbers must fail")

local duplicate = environment()
table.insert(duplicate, prefix .. "qpu=nwqsim")
output, err = module.directive({
	spank_job_env = duplicate,
	partition = "quantum",
})
check(output == nil and string.find(err, "duplicate"),
	"duplicates must fail")

output, err = module.directive({
	spank_job_env = environment({qpu = "missing"}),
	partition = "quantum",
})
check(output == nil and string.find(err, "unknown QPU"),
	"unknown resources must fail")

local quantum = {
	spank_job_env = environment(),
	partition = "quantum",
	account = "qfw-test",
}
check(slurm_job_submit(quantum, nil, 0) == slurm.SUCCESS,
	"a quantum job with an account must be accepted")
check(quantum.burst_buffer == "#QFW v=1 qpu=nwqsim-site workload=quantum " ..
	"circuits=2 qubits=5 depth=120 shots=1024", quantum.burst_buffer)

local unaccounted = {spank_job_env = environment(), partition = "quantum"}
check(slurm_job_submit(unaccounted, nil, 0) == slurm.ERROR,
	"a quantum job without an account must fail")
check(unaccounted.burst_buffer == nil,
	"a refused quantum job must not get a directive")

local ordinary = {spank_job_env = nil, partition = "quantum"}
check(slurm_job_submit(ordinary, nil, 0) == slurm.SUCCESS,
	"an ordinary job without an account must be accepted")
check(ordinary.burst_buffer == nil, "ordinary jobs must be unchanged")

local ordinary_env = {spank_job_env = {"OTHER=1"}, partition = "quantum",
	account = ""}
check(slurm_job_submit(ordinary_env, nil, 0) == slurm.SUCCESS,
	"an ordinary job with an empty account must be accepted")

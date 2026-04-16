from pathlib import Path
import sys


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    repo_dir = base_dir.parent / "SustainDC"
    sys.path.insert(0, str(repo_dir))

    from utils.managers import Time_Manager, Workload_Manager
    from envs.carbon_ls import CarbonLoadEnv

    workload_manager = Workload_Manager(
        workload_filename="Alibaba_CPU_Data_Hourly_1.csv",
        init_day=0,
    )
    time_manager = Time_Manager(init_day=0, days_per_episode=1)
    workload_env = CarbonLoadEnv(test_mode=True)

    time_manager.reset(init_day=0, init_hour=0)
    current_workload = workload_manager.reset(init_day=0, init_hour=0)

    workload_env.update_current_date(time_manager.day, time_manager.hour)
    workload_env.update_workload(current_workload)
    state, info = workload_env.reset()

    print("Standalone Workload Run")
    print(f"repo_dir={repo_dir}")
    print(f"initial_workload={float(current_workload):.4f}")
    print(f"state_dim={len(state)}")
    print(f"queue_max_len={info['ls_queue_max_len']}")
    print("-" * 72)

    actions = [1, 0, 0, 2, 1, 2, 0, 1]

    for idx, action in enumerate(actions, start=1):
        workload = workload_manager.step()
        day, hour, _, _ = time_manager.step()

        workload_env.update_current_date(day, hour)
        workload_env.update_workload(workload)

        state, reward, terminated, truncated, info = workload_env.step(action)

        print(
            f"step={idx:02d} "
            f"action={action} "
            f"day={day} hour={hour:05.2f} "
            f"workload={float(workload):.4f} "
            f"shifted={info['ls_shifted_workload']:.4f} "
            f"queue={info['ls_tasks_in_queue']:03d} "
            f"overdue={info['ls_overdue_penalty']}"
        )

    print("-" * 72)
    print("Standalone workload loop finished successfully.")


if __name__ == "__main__":
    main()

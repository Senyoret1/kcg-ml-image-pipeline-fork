
import argparse
import sys
import time
import threading

base_directory = "./"
sys.path.insert(0, base_directory)

from prompt_job_generator_state import PromptJobGeneratorState
from prompt_job_generator_functions import generate_icon_generation_jobs, generate_character_generation_jobs, generate_mechs_image_generation_jobs, generate_propaganda_posters_image_generation_jobs
from prompt_job_generator.http_requests.request import http_get_all_dataset_rate, http_get_in_progress_jobs_count, http_get_pending_jobs_count, http_get_dataset_list


def parse_args():
    parser = argparse.ArgumentParser(description="generate prompts")

    # Required parameters
    parser.add_argument("--base_prompts_path", type=str)

    return parser.parse_args()


def update_dataset_prompt_queue(prompt_job_generator_state, list_datasets):
    # if dataset list is null return
    if list_datasets is None:
        return

    prompt_queue = prompt_job_generator_state.prompt_queue

    for dataset in list_datasets:
        prompt_queue.update(prompt_job_generator_state, dataset)

def update_dataset_rates(prompt_job_generator_state, list_datasets):

    # if dataset list is null return
    if list_datasets is None:
        return

    dataset_rate_json = http_get_all_dataset_rate()
    dataset_rate_dictionary = {}

    for dataset_rate in dataset_rate_json:
        dataset = dataset_rate['dataset_name']
        dataset_rate = dataset_rate['dataset_rate']

        dataset_rate_dictionary[dataset] = dataset_rate

    # loop through all datasets and
    # for each dataset update the dataset_rate
    # from orchestration api rates
    total_rate = 0
    for dataset in list_datasets:

        if dataset not in dataset_rate_dictionary:
            continue

        dataset_rate = int(dataset_rate_dictionary[dataset])

        total_rate += dataset_rate

        prompt_job_generator_state.set_dataset_rate(dataset, dataset_rate)

    prompt_job_generator_state.set_total_rate(total_rate)


def update_dataset_job_queue_size(prompt_job_generator_state, list_datasets):

    # if dataset list is null return
    if list_datasets is None:
        return

    # hard coded for now
    # TODO use orchestration api to get those values
    dataset_job_per_second_dictionary = {
        'icons': 0.2,
        'character': 0.2,
        'mech': 0.2,
        'propaganda-poster': 0.5,
        'environmental': 0.5
    }

    # loop through all datasets and
    # for each dataset update the job_queue_size & job_queue_target
    # from orchestration api rates
    for dataset in list_datasets:

        # get the number of jobs available for the dataset
        in_progress_job_count = http_get_in_progress_jobs_count(dataset)
        pending_job_count = http_get_pending_jobs_count(dataset)

        if in_progress_job_count is None or pending_job_count is None:
            continue

        if dataset in dataset_job_per_second_dictionary:
            dataset_job_per_second = dataset_job_per_second_dictionary[dataset]
        else:
            dataset_job_per_second = None

        if dataset_job_per_second is None:
            continue

        job_queue_size = in_progress_job_count + pending_job_count
        # Target number of Jobs in Queue
        # Equals: Time Speed (Jobs/Second) times 60*5 (300); 5 minutes
        job_queue_target = 60 * 5 * dataset_job_per_second

        prompt_job_generator_state.set_dataset_job_queue_size(dataset, job_queue_size)
        prompt_job_generator_state.set_dataset_job_queue_target(dataset, job_queue_target)

def update_dataset_prompt_queue_background_thread(prompt_job_generator_state):

    while True:
        # get list of datasets
        list_datasets = http_get_dataset_list()

        update_dataset_prompt_queue(prompt_job_generator_state, list_datasets)

        sleep_time_in_seconds = 1.0
        time.sleep(sleep_time_in_seconds)

def update_dataset_values_background_thread(prompt_job_generator_state):

    while True:
        # get list of datasets
        list_datasets = http_get_dataset_list()

        update_dataset_rates(prompt_job_generator_state, list_datasets)
        update_dataset_job_queue_size(prompt_job_generator_state, list_datasets)

        sleep_time_in_seconds = 1.0
        time.sleep(sleep_time_in_seconds)

def main():
    args = parse_args()

    device = 'cuda'
    minio_access_key = 'v048BpXpWrsVIHUfdAix'
    minio_secret_key = '4TFS20qkxVuX2HaC8ezAgG7GaDlVI1TqSPs0BKyu'
    csv_dataset_path = 'input/civitai_phrases_database_v6.csv'
    csv_phrase_limit = 0

    prompt_job_generator_state = PromptJobGeneratorState(device=device)

    prompt_job_generator_state.configure_minio(minio_access_key, minio_secret_key)
    prompt_job_generator_state.load_clip_model()

    # loading civitai prompt csv file
    prompt_job_generator_state.load_prompt_list_from_csv(csv_dataset_path, csv_phrase_limit)

    # Adding dataset masks
    prompt_job_generator_state.add_dataset_mask("icons", "./test/test_inpainting/white_512x512.jpg", "./test/test_inpainting/icon_mask.png")
    prompt_job_generator_state.add_dataset_mask("character", "./test/test_inpainting/white_512x512.jpg", "./test/test_inpainting/character_mask.png")

    # register function callbacks
    # used to spawn jobs for each job_type/dataset
    prompt_job_generator_state.register_callback("icons", generate_icon_generation_jobs)
    prompt_job_generator_state.register_callback("propaganda-poster", generate_propaganda_posters_image_generation_jobs)
    prompt_job_generator_state.register_callback("mech", generate_mechs_image_generation_jobs)
    prompt_job_generator_state.register_callback("character", generate_character_generation_jobs)

    prompt_job_generator_state.load_efficient_net_model('character', 'datasets',
                                          'character/models/ranking/ab_ranking_efficient_net/2023-10-10.pth')

    # setting the base prompt csv for each dataset
    prompt_job_generator_state.prompt_queue.set_dataset_base_prompt('icons',
                                                                    'input/dataset-config/icon/base-prompts-icon-2.csv')
    prompt_job_generator_state.prompt_queue.set_dataset_base_prompt('propaganda-poster',
                                                                    'input/dataset-config/propaganda-poster/base-prompts-propaganda-poster.csv')
    prompt_job_generator_state.prompt_queue.set_dataset_base_prompt('mech',
                                                                    'input/dataset-config/mech/base-prompts-mechs.csv')
    prompt_job_generator_state.prompt_queue.set_dataset_base_prompt('character',
                                                                    'input/dataset-config/character/base-prompts-waifu.csv')
    prompt_job_generator_state.prompt_queue.set_dataset_base_prompt('environmental',
                                                                    'input/dataset-config/icon/base-prompts-icon-2.csv')

    # get list of datasets
    list_datasets = http_get_dataset_list()
    update_dataset_prompt_queue(prompt_job_generator_state, list_datasets)

    thread = threading.Thread(target=update_dataset_values_background_thread, args=(prompt_job_generator_state,))
    thread.start()

    thread = threading.Thread(target=update_dataset_prompt_queue_background_thread, args=(prompt_job_generator_state,))
    thread.start()

    while True:

        # dictionary that maps dataset => number of jobs to add
        dataset_number_jobs_to_add = {}

        for dataset in list_datasets:
            dataset_rate = prompt_job_generator_state.get_dataset_rate(dataset)
            dataset_job_queue_size = prompt_job_generator_state.get_dataset_job_queue_size(dataset)
            dataset_job_queue_target = prompt_job_generator_state.get_dataset_job_queue_target(dataset)

            # if dataset_rate is not found just move on
            if dataset_rate == None:
                print("dataset rate not found for dataset ", dataset)
                continue

            if dataset_job_queue_size is None:
                print("dataset job queue size is not found for dataset : ", dataset)
                continue

            if dataset_job_queue_target is None:
                print("dataset job queue target is not found for dataset : ", dataset)
                continue

            number_of_jobs_to_add = 0

            if dataset_job_queue_target > dataset_job_queue_size:
                number_of_jobs_to_add = dataset_job_queue_target - dataset_job_queue_size

            dataset_number_jobs_to_add[dataset] = number_of_jobs_to_add


        # If JobQueueSize < JobQueueTarget
        #- then keep "updating"/ adding
        #- for each Dataset, TodoJob[i] += DatasetRate[i] / TotalRate
        #- then at end of loop, if >1.0, then emit job for that dataset
        dataset_todo_jobs = {}
        for dataset in list_datasets:
            dataset_todo_jobs[dataset] = 0

        # Make sure we stop lopping
        # If there are no added jobs
        added_atleast_one_job = True

        while added_atleast_one_job:
            added_atleast_one_job = False

            for dataset in list_datasets:
                # get dataset rate
                # dataset rates should update in background using
                # orchestration api
                dataset_rate = prompt_job_generator_state.get_dataset_rate(dataset)

                # if dataset_rate does not exist skip this dataset
                if dataset_rate is None:
                    continue

                if dataset not in dataset_number_jobs_to_add:
                    continue

                if not prompt_job_generator_state.prompt_queue.database_prompt_available(dataset):
                    print('no prompt is available for dataset ', dataset)
                    continue

                # get dataset callback
                # used to spawn the job
                # if the callback is not found
                # just move on
                dataset_callback = prompt_job_generator_state.get_callback(dataset)

                if dataset_callback == None:
                    print("dataset callback not found for dataset ", dataset)
                    continue

                number_of_jobs_to_add = dataset_number_jobs_to_add[dataset]

                if number_of_jobs_to_add > 0:
                    dataset_todo_jobs[dataset] += dataset_rate
                    added_atleast_one_job = True

                if dataset_todo_jobs[dataset] >= 1.0:
                    # spawn job
                    dataset_todo_jobs[dataset] -= 1.0
                    dataset_number_jobs_to_add[dataset] = number_of_jobs_to_add - 1

                    print(f'number of jobs to spawn for dataset {dataset} is {number_of_jobs_to_add}')
                    # Adding a job
                    dataset_callback(prompt_job_generator_state)

        # sleep for n number of seconds
        time_to_sleep_in_seconds = 2

        time.sleep(time_to_sleep_in_seconds)

if __name__ == '__main__':
    main()
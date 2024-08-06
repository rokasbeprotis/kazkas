import subprocess

def update_requirements():
    # Run pip freeze and write output to requirements.txt
    with open('requirements.txt', 'w') as f:
        subprocess.run(['pip', 'freeze'], stdout=f)

if __name__ == "__main__":
    update_requirements()
    print("requirements.txt has been updated.")
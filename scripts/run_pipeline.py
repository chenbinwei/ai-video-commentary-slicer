"""Run the full video slicing pipeline.

Use:
    python -m scripts.run_pipeline --input videos/input.mp4 --context context.json
"""

from video_slicer.pipeline import main


if __name__ == "__main__":
    main()

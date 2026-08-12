from pathlib import Path
import shutil

from PIL import Image

from app import ratio_stitch_image, ratio_stitch_plan, safe_ratio_stitch_name


def main() -> None:
    first = ratio_stitch_plan(3072, 1024, 500, 43)
    assert first == {
        "repeat_count": 4,
        "stitched_width": 12288,
        "stitched_height": 1024,
        "crop_width": 11907,
        "crop_height": 1024,
        "crop_left": 190,
        "crop_right": 191,
    }

    second = ratio_stitch_plan(5908, 2539, 500, 43)
    assert second["repeat_count"] == 5
    assert second["crop_width"] == 29523
    assert second["crop_left"] == 8
    assert second["crop_right"] == 9

    image = Image.new("RGBA", (300, 100), (20, 120, 180, 255))
    result, plan = ratio_stitch_image(image, 500, 43)
    assert plan["repeat_count"] == 4
    assert result.size == (1163, 100)
    assert safe_ratio_stitch_name("海浪.png", "_500x43", 500, 43) == "海浪_500x43.png"

    temp = Path(__file__).resolve().parent / ".ratio_stitch_test"
    shutil.rmtree(temp, ignore_errors=True)
    temp.mkdir()
    output = temp / "result.png"
    result.save(output)
    with Image.open(output) as saved:
        assert saved.size == (1163, 100)
    shutil.rmtree(temp, ignore_errors=True)
    print("ratio stitch tests passed")


if __name__ == "__main__":
    main()

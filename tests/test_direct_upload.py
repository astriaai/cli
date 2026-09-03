import io
import runpy
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


CLI = runpy.run_path(Path(__file__).parents[1] / "astria", run_name="astria_test")


class DirectUploadTest(unittest.TestCase):
    def test_tune_create_direct_uploads_local_images_as_signed_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "look.jpg"
            image.write_bytes(b"image")
            captured = []

            def request(_cfg, method, path, **kwargs):
                captured.append((method, path, kwargs))
                return {"id": 7}

            args = SimpleNamespace(
                title="Look", name="dress", model_type="faceid", model="123",
                description=None, image_url=None, image=[str(image)], workspace=None,
            )
            with patch.dict(CLI["cmd_tunes_create"].__globals__, {
                "direct_uploads": lambda _cfg, _paths: ["signed-blob"],
                "request": request,
            }):
                with redirect_stdout(io.StringIO()):
                    CLI["cmd_tunes_create"](args, {})

        form = captured[0][2]["form"]
        self.assertIn(("tune[images][]", "signed-blob"), form)
        self.assertNotIn(f"@{image}", [value for _, value in form])

    def test_direct_uploads_run_in_parallel_and_return_input_order(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for index in range(4):
                path = Path(directory) / f"{index}.jpg"
                path.write_bytes(b"image")
                paths.append(str(path))

            lock = threading.Lock()
            active = 0
            max_active = 0

            def upload(_cfg, prepared):
                nonlocal active, max_active
                with lock:
                    active += 1
                    max_active = max(max_active, active)
                time.sleep(0.02 * (4 - int(prepared[0].stem)))
                with lock:
                    active -= 1
                return f"signed-{prepared[0].stem}"

            with patch.dict(CLI["direct_uploads"].__globals__, {
                "DIRECT_UPLOAD_WORKERS": 2,
                "perform_direct_upload": upload,
            }):
                result = CLI["direct_uploads"]({}, paths)

        self.assertEqual(max_active, 2)
        self.assertEqual(result, ["signed-0", "signed-1", "signed-2", "signed-3"])

    def test_direct_upload_records_retain_public_urls_in_input_order(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for index in range(2):
                path = Path(directory) / f"{index}.jpg"
                path.write_bytes(b"image")
                paths.append(str(path))

            def upload(_cfg, prepared):
                stem = prepared[0].stem
                return {"signed_id": f"signed-{stem}", "public_url": f"https://cdn.test/{stem}.jpg"}

            with patch.dict(CLI["direct_upload_records"].__globals__, {
                "perform_direct_upload_record": upload,
            }):
                result = CLI["direct_upload_records"]({}, paths)

        self.assertEqual(result, [
            {"signed_id": "signed-0", "public_url": "https://cdn.test/0.jpg"},
            {"signed_id": "signed-1", "public_url": "https://cdn.test/1.jpg"},
        ])

    def test_direct_uploads_validate_every_file_before_uploading(self):
        upload = Mock()
        with tempfile.TemporaryDirectory() as directory:
            present = Path(directory) / "present.jpg"
            present.write_bytes(b"image")
            missing = Path(directory) / "missing.jpg"

            with patch.dict(CLI["direct_uploads"].__globals__, {"perform_direct_upload": upload}):
                with self.assertRaises(SystemExit):
                    CLI["direct_uploads"]({}, [str(present), str(missing)])

        upload.assert_not_called()

    def test_perform_direct_upload_uses_presigned_headers_and_file_body(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "clip.mov"
            video.write_bytes(b"video")
            request = Mock(return_value={
                "signed_id": "signed-video",
                "direct_upload": {
                    "url": "https://r2.example.com/upload",
                    "headers": {"Content-Type": "video/quicktime", "Content-MD5": "checksum"},
                },
            })
            subprocess_run = Mock(return_value=SimpleNamespace(
                returncode=0, stdout=b"\n200", stderr=b"",
            ))

            with patch.dict(CLI["perform_direct_upload"].__globals__, {
                "request": request,
                "subprocess": SimpleNamespace(run=subprocess_run),
            }):
                result = CLI["perform_direct_upload"]({}, CLI["prepare_direct_upload"](str(video)))

        self.assertEqual(result, "signed-video")
        self.assertEqual(request.call_args.args[1:3], ("POST", "/api/direct_uploads"))
        self.assertEqual(request.call_args.kwargs["json_body"]["blob"]["content_type"], "video/quicktime")
        argv = subprocess_run.call_args.args[0]
        self.assertIn("Content-Type: video/quicktime", argv)
        self.assertIn("Content-MD5: checksum", argv)
        self.assertIn(f"@{video}", argv)
        self.assertEqual(argv[-1], "https://r2.example.com/upload")

    def test_generate_direct_uploads_input_and_mask_before_prompt_request(self):
        with tempfile.TemporaryDirectory() as directory:
            input_image = Path(directory) / "input.jpg"
            mask_image = Path(directory) / "mask.png"
            input_image.write_bytes(b"input")
            mask_image.write_bytes(b"mask")
            upload = Mock(return_value=["signed-input", "signed-mask"])
            request = Mock(return_value={"id": 9})
            args = SimpleNamespace(
                model="123", references=[], text="edit", num_images="1", seed=None,
                film_grain=None, aspect_ratio="1:1", resolution=None,
                input_image=str(input_image), mask_image=str(mask_image), pack_id=None,
                base_pack_id=None, workspace=None, wait=False,
            )

            with patch.dict(CLI["_generate"].__globals__, {
                "direct_uploads": upload,
                "request": request,
            }):
                with redirect_stdout(io.StringIO()):
                    CLI["_generate"](args, {}, video=False)

        upload.assert_called_once_with({}, [str(input_image), str(mask_image)])
        form = request.call_args.kwargs["form"]
        self.assertIn(("prompt[input_image]", "signed-input"), form)
        self.assertIn(("prompt[mask_image]", "signed-mask"), form)
        self.assertFalse(any(str(value).startswith("@") for _, value in form))

    def test_video_direct_uploads_all_local_media_in_one_ordered_batch(self):
        with tempfile.TemporaryDirectory() as directory:
            names = ["reference.jpg", "look.jpg", "first.jpg", "last.jpg", "motion.mp4", "audio.mp3"]
            paths = []
            for name in names:
                path = Path(directory) / name
                path.write_bytes(name.encode())
                paths.append(str(path))
            upload = Mock(return_value=[f"signed-{index}" for index in range(len(paths))])
            calls = []

            def request(_cfg, method, path, **kwargs):
                calls.append((method, path, kwargs))
                return {"id": 7, "name": "dress"} if path == "/tunes" else {"id": 9}

            args = SimpleNamespace(
                model="123", references=[f"dress={paths[0]}"], text=None,
                num_images="1", seed=None, film_grain=None, aspect_ratio="16:9",
                resolution=None, input_image=None, mask_image=None, pack_id=None,
                base_pack_id=None, video_model="seedance2_fast_720p",
                video_prompt="dress moves", duration="5", image_references=[paths[1]],
                first_frame=paths[2], last_frame=paths[3], input_video=paths[4],
                audio_reference=paths[5], generate_audio=None, workspace=None, wait=False,
            )

            with patch.dict(CLI["_generate"].__globals__, {
                "direct_uploads": upload,
                "request": request,
            }):
                with redirect_stdout(io.StringIO()):
                    CLI["_generate"](args, {}, video=True)

        upload.assert_called_once_with({}, paths)
        self.assertEqual(calls[0][1], "/tunes")
        self.assertIn(("tune[images][]", "signed-0"), calls[0][2]["form"])
        prompt_form = calls[1][2]["form"]
        self.assertIn(("prompt[image_references][]", "signed-1"), prompt_form)
        self.assertIn(("prompt[video_first_frame]", "signed-2"), prompt_form)
        self.assertIn(("prompt[video_last_frame]", "signed-3"), prompt_form)
        self.assertIn(("prompt[input_video]", "signed-4"), prompt_form)
        self.assertIn(("prompt[audio_reference]", "signed-5"), prompt_form)
        self.assertFalse(any(str(value).startswith("@") for _, value in prompt_form))

    def test_pack_run_direct_uploads_training_images_before_api_call(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.jpg"
            second = Path(directory) / "second.jpg"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            upload = Mock(return_value=["signed-first", "signed-second"])
            request = Mock(return_value={"id": 7})
            args = SimpleNamespace(
                slug="lookbook", tune_id=None, title="Look", name="dress",
                image=[str(first), str(second)], image_url=None, brief=None,
                prompt_ids=None, num_images=None, aspect_ratio=None, resolution=None,
                inpaint_faces=None, attr=None, workspace=None,
            )

            with patch.dict(CLI["cmd_packs_run"].__globals__, {
                "direct_uploads": upload,
                "request": request,
            }):
                with redirect_stdout(io.StringIO()):
                    CLI["cmd_packs_run"](args, {})

        upload.assert_called_once_with({}, [str(first), str(second)])
        images = [value for key, value in request.call_args.kwargs["form"] if key == "tune[images][]"]
        self.assertEqual(images, ["signed-first", "signed-second"])

    def test_raw_api_direct_uploads_file_forms_and_preserves_field_order(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.jpg"
            second = Path(directory) / "second.jpg"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            upload = Mock(return_value=["signed-first", "signed-second"])
            request = Mock(return_value={"id": 7})
            args = SimpleNamespace(
                form=[f"tune[images][]=@{first}", "tune[title]=Look", f"tune[images][]=@{second}"],
                query=None, data=None, method="POST", path="/tunes", workspace=None,
            )

            with patch.dict(CLI["cmd_api"].__globals__, {
                "direct_uploads": upload,
                "request": request,
            }):
                with redirect_stdout(io.StringIO()):
                    CLI["cmd_api"](args, {})

        upload.assert_called_once_with({}, [str(first), str(second)])
        self.assertEqual(request.call_args.kwargs["form"], [
            ("tune[images][]", "signed-first"),
            ("tune[title]", "Look"),
            ("tune[images][]", "signed-second"),
        ])

    def test_upload_failure_prevents_generation_api_calls(self):
        request = Mock()
        args = SimpleNamespace(
            model="123", references=[], text="edit", num_images="1", seed=None,
            film_grain=None, aspect_ratio="1:1", resolution=None,
            input_image="input.jpg", mask_image=None, pack_id=None,
            base_pack_id=None, workspace=None, wait=False,
        )
        with patch.dict(CLI["_generate"].__globals__, {
            "direct_uploads": Mock(side_effect=CLI["AstriaError"]("upload failed")),
            "request": request,
        }):
            with self.assertRaises(CLI["AstriaError"]):
                CLI["_generate"](args, {}, video=False)

        request.assert_not_called()

    def test_inspect_video_direct_uploads_a_local_file(self):
        args = SimpleNamespace(source="clip.mp4", tune_id=["12", "13"], workspace="9")
        captured = {}

        def request(_cfg, method, path, **kwargs):
            captured.update(method=method, path=path, **kwargs)
            return {"description": "00-05 - shot"}

        with patch.dict(CLI["cmd_inspect_video"].__globals__, {
            "direct_upload": lambda _cfg, _path: "signed-video",
            "request": request,
        }):
            output = io.StringIO()
            with redirect_stdout(output):
                CLI["cmd_inspect_video"](args, {})

        self.assertEqual(captured["path"], "/videos/inspect")
        self.assertEqual(captured["json_body"], {
            "blob_signed_id": "signed-video",
            "tune_ids": [12, 13],
        })
        self.assertEqual(captured["timeout"], 125)
        self.assertEqual(__import__("json").loads(output.getvalue())["description"], "00-05 - shot")

    def test_inspect_video_passes_an_https_url_without_uploading(self):
        args = SimpleNamespace(source="https://example.com/clip.mp4", tune_id=None, workspace=None)
        request = Mock(return_value={"description": "00-05 - shot"})
        upload = Mock()

        with patch.dict(CLI["cmd_inspect_video"].__globals__, {
            "direct_upload": upload,
            "request": request,
        }):
            with redirect_stdout(io.StringIO()):
                CLI["cmd_inspect_video"](args, {})

        upload.assert_not_called()
        self.assertEqual(request.call_args.kwargs["json_body"], {
            "file_url": "https://example.com/clip.mp4",
        })

    def test_inspect_video_polls_until_the_inspection_settles(self):
        args = SimpleNamespace(source="https://example.com/clip.mp4", tune_id=None, workspace=None)
        calls = []

        def request(_cfg, method, path, **kwargs):
            calls.append((method, path))
            if method == "POST":
                return {"id": "abc123", "status": "pending"}
            if len(calls) < 3:
                return {"id": "abc123", "status": "processing"}
            return {"id": "abc123", "status": "completed", "description": "00-05 - shot"}

        with patch.dict(CLI["cmd_inspect_video"].__globals__, {
            "direct_upload": Mock(),
            "request": request,
            "time": SimpleNamespace(monotonic=lambda: 0.0, sleep=lambda _s: None),
        }):
            output = io.StringIO()
            with redirect_stdout(output):
                CLI["cmd_inspect_video"](args, {})

        self.assertEqual(calls, [
            ("POST", "/videos/inspect"),
            ("GET", "/videos/inspect/abc123"),
            ("GET", "/videos/inspect/abc123"),
        ])
        self.assertEqual(__import__("json").loads(output.getvalue())["status"], "completed")

    def test_inspect_video_reports_a_failed_inspection(self):
        args = SimpleNamespace(source="https://example.com/clip.mp4", tune_id=None, workspace=None)
        request = Mock(return_value={"id": "abc123", "status": "failed", "error": "Video is too large to inspect"})

        with patch.dict(CLI["cmd_inspect_video"].__globals__, {
            "direct_upload": Mock(),
            "request": request,
        }):
            with self.assertRaises(CLI["AstriaError"]) as raised:
                CLI["cmd_inspect_video"](args, {})

        self.assertIn("Video is too large to inspect", str(raised.exception))

    def test_parser_exposes_inspect_video_without_a_custom_prompt(self):
        args = CLI["build_parser"]().parse_args([
            "inspect-video", "clip.mp4", "--tune-id", "12",
        ])

        self.assertEqual(args.source, "clip.mp4")
        self.assertEqual(args.tune_id, ["12"])
        self.assertFalse(hasattr(args, "prompt"))


if __name__ == "__main__":
    unittest.main()

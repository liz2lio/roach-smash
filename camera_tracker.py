"""Standalone green-marker tracking test for Windows and macOS.

Run:
    python camera_tracker.py

This reports positions in CAMERA pixels. It is not yet calibrated to
the game window and does not control gameplay.
"""

from dataclasses import dataclass
import sys

import cv2
import numpy as np


@dataclass
class MarkerObservation:
    x: int
    y: int
    area: float


class CameraTracker:
    def __init__(
        self,
        camera_index=0,
        hsv_lower=(35, 80, 80),
        hsv_upper=(85, 255, 255),
        minimum_area=300,
    ):
        self.camera_index = camera_index
        self.hsv_lower = np.array(hsv_lower, dtype=np.uint8)
        self.hsv_upper = np.array(hsv_upper, dtype=np.uint8)
        self.minimum_area = minimum_area

        self.camera = None
        self.missed_frames = 0

    def open(self):
        # DirectShow is Windows-only. AVFoundation is the macOS backend.
        if sys.platform == "win32":
            backend = cv2.CAP_DSHOW
        elif sys.platform == "darwin":
            backend = cv2.CAP_AVFOUNDATION
        else:
            backend = cv2.CAP_ANY

        self.camera = cv2.VideoCapture(self.camera_index, backend)

        if not self.camera.isOpened():
            self.close()
            raise RuntimeError(
                f"Cannot open camera index {self.camera_index}. "
                "Check camera permissions, close other camera apps, "
                "or try a different camera index."
            )

    def read_marker(self):
        """Return (marker observation or None, annotated camera frame)."""
        if self.camera is None:
            raise RuntimeError("Call open() before read_marker().")

        success, frame = self.camera.read()

        if not success or frame is None:
            raise RuntimeError("Camera opened but supplied no video frame.")

        blurred = cv2.GaussianBlur(frame, (7, 7), 0)
        hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
        kernel = np.ones((5, 5), dtype=np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )

        observation = None

        if contours:
            contour = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(contour)

            if area >= self.minimum_area:
                moments = cv2.moments(contour)

                if moments["m00"] != 0:
                    x = int(moments["m10"] / moments["m00"])
                    y = int(moments["m01"] / moments["m00"])

                    observation = MarkerObservation(x, y, area)
                    self.missed_frames = 0

                    cv2.drawContours(
                        frame, [contour], -1, (0, 255, 0), 2
                    )
                    cv2.circle(frame, (x, y), 8, (0, 0, 255), -1)

        if observation is None:
            self.missed_frames += 1
            status = f"MARKER LOST ({self.missed_frames} frames)"
        else:
            status = (
                f"Marker: ({observation.x}, {observation.y}) "
                f"area={observation.area:.0f}"
            )

        cv2.putText(
            frame,
            status,
            (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

        return observation, frame

    def close(self):
        if self.camera is not None:
            self.camera.release()
            self.camera = None


def main():
    # Change to 1 if index 0 is not the intended camera.
    tracker = CameraTracker(camera_index=0)

    try:
        tracker.open()
        print("Camera open. Show a green marker. Press Q or Esc to quit.")

        while True:
            observation, frame = tracker.read_marker()

            if observation is not None:
                print(
                    f"\rMarker: x={observation.x}, "
                    f"y={observation.y}, "
                    f"area={observation.area:.0f}    ",
                    end="",
                    flush=True,
                )

            cv2.imshow("ROACH SMASH! - Marker Test", frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break

    except RuntimeError as error:
        print(f"\nCamera test failed: {error}")

    finally:
        tracker.close()
        cv2.destroyAllWindows()
        print("\nCamera released.")


if __name__ == "__main__":
    main()

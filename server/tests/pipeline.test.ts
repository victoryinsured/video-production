import { describe, expect, it } from "vitest";
import {
  downstreamOfLessonStep,
  downstreamOfResourceStep,
  stepIsLessonLevel,
  stepIsResourceLevel,
  INVALIDATION_TRIGGERS,
} from "../src/queue/pipeline";

describe("downstreamOfLessonStep", () => {
  it("a script edit's root (slides) pulls in video, aws_upload, bunny_upload, moodle_publish, and editable_assets", () => {
    const downstream = new Set(downstreamOfLessonStep("slides"));
    expect(downstream).toEqual(
      new Set(["video", "editable_assets", "aws_upload", "bunny_upload", "moodle_publish"])
    );
  });

  it("a voice-only change (narration) does not touch editable_assets", () => {
    const downstream = new Set(downstreamOfLessonStep("narration"));
    expect(downstream).toEqual(new Set(["video", "aws_upload", "bunny_upload", "moodle_publish"]));
    expect(downstream.has("editable_assets")).toBe(false);
  });

  it("editable_assets is terminal", () => {
    expect(downstreamOfLessonStep("editable_assets")).toEqual([]);
  });

  it("moodle_publish is terminal", () => {
    expect(downstreamOfLessonStep("moodle_publish")).toEqual([]);
  });

  it("aws_upload and bunny_upload both converge on moodle_publish alone", () => {
    expect(downstreamOfLessonStep("aws_upload")).toEqual(["moodle_publish"]);
    expect(downstreamOfLessonStep("bunny_upload")).toEqual(["moodle_publish"]);
  });
});

describe("downstreamOfResourceStep", () => {
  it("resource_upload leads to resource_moodle", () => {
    expect(downstreamOfResourceStep("resource_upload")).toEqual(["resource_moodle"]);
  });

  it("resource_moodle is terminal", () => {
    expect(downstreamOfResourceStep("resource_moodle")).toEqual([]);
  });
});

describe("step classification", () => {
  it("distinguishes lesson-level from resource-level steps", () => {
    expect(stepIsLessonLevel("video")).toBe(true);
    expect(stepIsLessonLevel("resource_upload")).toBe(false);
    expect(stepIsResourceLevel("resource_upload")).toBe(true);
    expect(stepIsResourceLevel("video")).toBe(false);
  });
});

describe("INVALIDATION_TRIGGERS", () => {
  it("a brand-only edit never invalidates narration", () => {
    expect(INVALIDATION_TRIGGERS.brandChanged).not.toContain("narration");
  });

  it("a voice-only edit never invalidates slides", () => {
    expect(INVALIDATION_TRIGGERS.voiceChanged).not.toContain("slides");
  });

  it("a video-description-only edit invalidates nothing in the render pipeline", () => {
    expect(INVALIDATION_TRIGGERS.videoDescriptionChanged).toEqual([]);
  });

  it("a manual video replacement re-triggers both upload destinations", () => {
    expect(new Set(INVALIDATION_TRIGGERS.manualVideoReplacement)).toEqual(new Set(["aws_upload", "bunny_upload"]));
  });
});

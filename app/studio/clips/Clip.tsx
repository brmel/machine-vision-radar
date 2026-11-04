import type { FC } from "react";
import { AbsoluteFill, Img, OffthreadVideo, Sequence, staticFile } from "remotion";
import { TYPE } from "../../src/ui/index.ts";
import { Frame, Zoomed, type Stamp } from "../cards/Frame.tsx";
import { END_SECONDS, FPS, HOOK_SECONDS, type ClipScript } from "./script.ts";

type Shown = { file: string; lead: number };
export type ClipProps = Stamp & ClipScript & { files: Shown[] };

export const CLIP_NONE: ClipProps = { address: "", asOf: null, hook: "", segments: [], about: [], files: [] };

const Footage: FC<Shown & Pick<ClipScript["segments"][number], "shows"
  | "caption">> = ({ file, lead, shows, caption }) => (
  <AbsoluteFill className="bg-page">
    {shows === "footage"
      ? <OffthreadVideo src={staticFile(file)} trimBefore={Math.round(lead * FPS)} muted
        className="size-full object-cover object-top" />
      : <Img src={staticFile(file)} className="size-full object-cover object-top" />}
    <AbsoluteFill>
      <Zoomed className={`p-8 flex flex-col justify-end ${shows === "card" ? "pb-24" : ""}`}>
        <p className={"self-start rounded-card border border-line bg-surface px-4 py-3 text-lead font-heading text-fg "
          + "shadow-overlay"}>{caption}</p>
      </Zoomed>
    </AbsoluteFill>
  </AbsoluteFill>
);

export const Clip: FC<ClipProps> = ({ address, asOf, hook, segments, files }) => {
  const starts =
    segments.reduce<number[]>((at, s) => [...at, at[at.length - 1] + s.seconds * FPS], [HOOK_SECONDS * FPS]);
  return (
    <AbsoluteFill className="bg-page">
      <Sequence durationInFrames={HOOK_SECONDS * FPS}>
        <Frame address={address} asOf={asOf}><p
          className={`h-full flex items-center ${TYPE.display}`}>{hook}</p></Frame>
      </Sequence>
      {segments.map((s, i) => (
        <Sequence key={s.shows} from={starts[i]} durationInFrames={s.seconds * FPS}>
          <Footage {...files[i]} shows={s.shows} caption={s.caption} />
        </Sequence>
      ))}
      <Sequence from={starts[starts.length - 1]} durationInFrames={END_SECONDS * FPS}>
        <Frame address={address} asOf={asOf}><p
          className={`h-full flex items-center font-mono ${TYPE.display}`}>{address}</p></Frame>
      </Sequence>
    </AbsoluteFill>
  );
};

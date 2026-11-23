# When a generated clip fails

A short diagnosis and repair order for generated video, condensed from
`references/failure-modes.md` in
[`4nrry/DirectorSKILL`](https://github.com/4nrry/DirectorSKILL) (fork of
`wuwangzhang1216/DirectorSKILL`, MIT). The thresholds are its planning
guidance, not rates measured here. Read the original for each code's causes
and prompt rewrites.

## Contents

- [Name the failure](#name-the-failure)
- [The cost ladder](#the-cost-ladder)
- [Three strikes: change the shot](#three-strikes-change-the-shot)
- [Plan around what never works](#plan-around-what-never-works)

## Name the failure

| Code | Failure | Code | Failure |
|---|---|---|---|
| F1 | identity drift | F11 | text or watermark artifacts |
| F2 | no motion (a slideshow) | F12 | lighting or color drift |
| F3 | warping, morph mush | F13 | speed wrong or ramping |
| F4 | wrong or absent action | F14 | physics (weight, collision, liquid) |
| F5 | no end state | F15 | audio or lip-sync mismatch |
| F6 | camera chaos, unrequested move | F16 | style drift |
| F7 | continuity break across shots | F17 | framing or crop error |
| F8 | anachronism | F18 | seam on an extend or loop |
| F9 | extra people or objects | F19 | an object vanishes or changes |
| F10 | anatomy (hands, limbs, teeth) | | |

Infer the code from what you already have, in this order, before asking
anything:

1. **The intended last frame.** If no one can say it in one sentence, it is
   F5: the prompt never had an end state.
2. **The input.** Image-to-video from a good still points at the prompt or
   the duration (F2, F4, F5, F13); from a soft or warped still, at the asset
   (F1, F3, F16), which no prompt fixes.
3. **When it breaks.** From frame 1: the keyframe or framing. After about
   60–70% of the clip: the model ran out of budget (F1, F3, F19). At a join:
   F18.
4. **The prompt.** More than one main verb predicts F4 or F5; more than one
   camera verb, F6.
5. **Same way every time?** Then it is deterministic: fix the prompt, the
   still or the plan, not the seed.

## The cost ladder

Climb from the top; each rung throws away more work than the one above.

| Rung | Move | Usually fixes |
|---|---|---|
| L1 | Edit the prompt | F2, F4, F5, F6, F9, F11, F13, F19 |
| L2 | Change a parameter: shorter, less motion, seed locked | F1, F3, F6, F13, F19 |
| L3 | Regenerate unchanged, at most twice | F3, F9, F10 when they come and go |
| L4 | Rebuild the still | F1, F8, F11, F12, F16, F17 |
| L4.5 | Video-to-video pass on the take (relight, regrade, reframe) | F12, F16, F17 |
| L5 | Re-plan the shot: shorter, closer, simpler, split | F14, F15, F19, anything below |
| L6 | Fix in the edit: trim, cutaway, retime, mask | F5, F13, F18, late F3 |
| L7 | Cut the shot | anything, once one shot has eaten about 8% of the budget |

- Two unchanged pulls that fail the same way mean the failure is
  deterministic: stop pulling.
- Go straight to L5 when the shot needs something from the last section, two
  codes show at once, the action needs more than about 1.5 s of precise
  contact, or three generations are already spent.
- A 0.5 s trim before the melt beats a fourth generation.

## Three strikes: change the shot

After three failed generations of one shot design, change the design, not
the wording. Pick one move and generate once:

| Move | Do | For |
|---|---|---|
| Shorten | cut 40–50% of the length, keep the action | late F1, F3, F18 |
| Push in | one size closer, two for anatomy | F3, F9, F10, F17 |
| Simplify | one motion only, camera locked | F4, F6, F13 |
| Split | two clips joined on a cut | F5, F14, F19 |
| First and last frame | both ends as stills | F5, F7, F19 |
| Substitute | a reaction or insert that implies it | F10, F14, F15 |
| Off-screen | the action leaves frame, show its result | F14, F10 |

## Plan around what never works

These fail across models whatever the prompt; get the story value another
way.

- **Precise hand work** past about 1.5 s (tying, writing, an instrument):
  intent, cut to the result, cut to the face.
- **A hand using a branded product:** keep the product still and move the
  light; give the hand its own clip under 1.5 s; composite the real product
  where the mark or color must be exact.
- **Readable text** (signs, screens, labels): out of focus, at an angle, or
  under three characters; carry the words by voice or a composited card.
- **Two people touching** (handshake, hug, fight): two singles joined on the
  contact.
- **One prop surviving 8 s or an occlusion:** keep it in frame, clips of 5 s
  or less, or let the reveal be a cut.
- **Reflections** that must match their subject: shoot only the reflection,
  or break the surface (rain, steam, a dark mirror).
- **Crowds** of faces that stay the same: silhouettes, backs of heads, bokeh
  or motion blur, at most two named faces per frame, crowd wides under 3 s.

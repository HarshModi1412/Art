# Apple Design Language & Rules - iOS, iPadOS, macOS

**Complete rulebook, captured from Apple's Human Interface Guidelines and current as of 15 September 2026.**

This is the design language Apple ships today: **Liquid Glass**, introduced with iOS 26 / iPadOS 26 / macOS 26 (Tahoe) and refined in **iOS 27 / iPadOS 27 / macOS 27 ("Golden Gate")**, which was announced at WWDC on 8 June 2026 and released on 14 September 2026 - yesterday.

## 0. How to read this, and how it was sourced

Every rule below is taken from Apple's own Human Interface Guidelines (HIG), read page by page directly from `developer.apple.com/design/human-interface-guidelines`. Rules are numbered so you can cite them in reviews (`TYP-4`, `A11Y-7`, and so on).

Four conventions used throughout:

- **MUST** - Apple states it as a requirement, or breaking it causes App Review rejection or a broken experience.
- **SHOULD** - Apple's stated recommendation. Deviating needs a reason.
- **NEVER** - Apple explicitly says don't.
- **[27]** - new or changed in the iOS 27 / iPadOS 27 / macOS 27 cycle. Items marked **[27-press]** come from release notes and press coverage rather than the HIG text itself, and are flagged separately in §10 so you know which claims are second-hand.

Where Apple gives a number (a point size, a contrast ratio, a tap-target dimension), the number is reproduced exactly. Where Apple deliberately gives no number - Liquid Glass corner radii, blur radii, spring constants - this document says so rather than inventing one. **Apple does not publish numeric values for Liquid Glass opacity, blur radius, or corner radii.** Anyone quoting you a specific figure for those is guessing.

Platform scope: this covers iOS, iPadOS and macOS. Rules that exist only for watchOS, tvOS or visionOS are omitted, except where they explain a principle that also applies to the three platforms in scope.

---


---

## Contents

| § | Section | What's in it |
|---|---|---|
| 1 | **The seven design principles** | Purpose, Agency, Responsibility, Familiarity, Flexibility, Simplicity, Craft, Delight |
| 2 | **Liquid Glass** | The two-layer model, regular vs clear, colour on glass, standard materials, motion |
| 3 | **Platform character** | What iOS, iPadOS and macOS each are, and the rules that follow |
| 4 | **Foundations** | Layout, typography, colour, Dark Mode, icons, app icons, SF Symbols, images, motion, accessibility, inclusion, right-to-left, writing, branding, privacy |
| 5 | **Component rules** | 36 components, from buttons and toolbars to charts and panels |
| 6 | **Interaction patterns** | Launching, onboarding, loading, feedback, modality, help, data entry, search, settings, undo, drag and drop, multitasking, full screen, file management |
| 7 | **Input rules** | Gestures, keyboards, pointing devices, focus, Apple Pencil and Scribble |
| 8 | **System experiences** | Notifications, widgets, controls, Live Activities, accounts, ratings |
| 9 | **What changed in iOS 27 / iPadOS 27 / macOS 27** | HIG-verified changes, press-sourced changes, and what they mean in practice |
| 10 | **The numbers, in one place** | Every published figure for these three platforms |
| 11 | **Review checklist** | A screen-by-screen audit, each item mapped to a rule |

## 1. The seven design principles

Apple reorganised its foundations around seven named principles. They are the tie-breakers when two rules pull in opposite directions.

| # | Principle | The one-line version | What it asks of you |
|---|---|---|---|
| **PRI-1** | **Purpose** | Make something meaningful | Identify what matters most to the people you're designing for, make those things great |
| **PRI-2** | **Agency** | Let people do things their own way | Freedom to act, kept informed, easy recovery from mistakes |
| **PRI-3** | **Responsibility** | Act in people's best interest | Prioritise safety and privacy, be transparent about what the product does and why |
| **PRI-4** | **Familiarity** | Build on what people know | Ground the experience in established physical and digital patterns, applied consistently |
| **PRI-5** | **Flexibility** | Adapt to diverse contexts and needs | Support as many devices, interaction types and perspectives as possible |
| **PRI-6** | **Simplicity** | Be clear and direct | Remove the unnecessary; every element earns its place |
| **PRI-7** | **Craft** | Care about every detail | Stunning visuals, smooth animation, precise wording, thoughtful audio |
| **PRI-8** | **Delight** | Make it human | Identify the emotion that's right for the experience and deliver it |

The expanded rules under each:

**Purpose**
- **PRI-1.1** At every stage of development, ask what the product is *for* and whether the design serves that purpose.
- **PRI-1.2** Prioritise the most important features by aligning with how people want to use the app, and make those features truly great.
- **PRI-1.3** Investigate existing solutions and avoid re-creating them. Define what sets your product apart.

**Agency**
- **PRI-2.1** **Stay out of the way.** Get people directly to the task or content at hand. The best designs are unobtrusive and present when people need them.
- **PRI-2.2** Let people move through the interface and access features without being locked into specific flows or modes. When a guided flow is necessary, make it easy to skip or escape.
- **PRI-2.3** **Build forgiveness in.** When people know they can reverse an action or return to a previous state, they feel free to explore. Recovering from the unexpected must not cost people their time or work.

**Responsibility**
- **PRI-3.1** Make the app's intentions clear from the very first interaction. Provide a clear rationale when asking for permission.
- **PRI-3.2** Collect only what the product needs to function. Anticipate ways data could be misused or cause harm and put protections in place.

**Familiarity**
- **PRI-4.1** Draw on both the real world and other software to make the interface feel familiar.
- **PRI-4.2** Once you establish a behaviour or appearance for an element, apply it throughout. Consistency helps people learn faster and gives them confidence that new interactions will work as expected.
- **PRI-4.3** Give clear feedback: show when controls are available, indicate when content changes, use system patterns for alerts and choices.

**Flexibility**
- **PRI-5.1** Treat accessibility as a priority **from the start**, not a retrofit.
- **PRI-5.2** **Preserve a person's context.** Keep content and controls in consistent, predictable positions across platforms and configurations; use natural animation to ease transitions.
- **PRI-5.3** Design for as many inputs as possible - voice, touch, keyboard, pointer, and more.
- **PRI-5.4** Give every platform you support the same level of care.

**Simplicity**
- **PRI-6.1** Simplicity isn't minimalism. Keep the important things close by and let the others fall away.
- **PRI-6.2** Be concise. Choose exactly the words you need to convey a concept or label a control.
- **PRI-6.3** Establish hierarchy. Prioritise recognisable controls and a consistent structure that tells people where they are and what comes next.

**Craft**
- **PRI-7.1** Be deliberate with each decision. Quality sets the tone.
- **PRI-7.2** Prototype early, try new approaches, discard what doesn't work. Test in real-world settings.
- **PRI-7.3** **Shipping isn't the finish line.** Keep the interface current with the latest platform capabilities and design patterns.

**Delight**
- **PRI-8.1** Know the feeling you want to evoke and let it shape the design.
- **PRI-8.2** Create defining moments - even an error message is an opportunity for character.
- **PRI-8.3** **Don't mistake delight for decoration.** People are trying to accomplish a task; don't let the pursuit of delight get in the way of the product's core purpose.
- **PRI-8.4** Delight emerges as the sum of consideration, not from any one flourish.

---

## 2. Liquid Glass - the design language itself

Liquid Glass is the material that unifies the design language across all Apple platforms. Understanding it structurally matters more than any single visual trick, because **it defines a two-layer model for every screen.**

### 2.1 The two-layer model

- **MAT-1** There is a **content layer** and a **functional layer**. Liquid Glass forms the functional layer - controls and navigation (tab bars, sidebars, toolbars) - and it **floats above** the content layer.
- **MAT-2** The point of the material is to let content scroll and peek through from beneath those elements, giving depth and dynamism while keeping controls legible.
- **MAT-3** **NEVER use Liquid Glass in the content layer.** Doing so creates unnecessary complexity and a confusing visual hierarchy. Use standard materials for content-layer elements such as app backgrounds.
  - The one exception: a control that lives in the content layer and has a *transient* interactive element - **sliders** and **toggles** - takes on a Liquid Glass appearance while a person is actively manipulating it, to emphasise interactivity.
- **MAT-4** **Use Liquid Glass sparingly.** Standard system components adopt it automatically. If you apply it to a *custom* control, limit it to the most important functional elements. Overusing it across multiple custom controls distracts from the content the material exists to reveal.

### 2.2 The two variants: regular and clear

- **MAT-5** Liquid Glass ships in two variants: **regular** and **clear**.
- **MAT-6** **Regular** blurs and adjusts the luminosity of background content to keep foreground text legible. Scroll edge effects further help by blurring and reducing the opacity of background content. **Most system components use this variant.** Use regular when: background content might create legibility problems, **or** the component carries a significant amount of text - alerts, sidebars, popovers.
- **MAT-7** **Clear** is highly translucent, for prioritising the visibility of underlying content. Use clear **only** for components floating above visually rich backgrounds - photos, video - to create a more immersive content experience.
- **MAT-8** With clear Liquid Glass over **bright** underlying content, add a **dark dimming layer at 35% opacity** behind the component. This is the one hard opacity number Apple publishes for the material.
- **MAT-9** With clear Liquid Glass over sufficiently **dark** content - or when using standard AVKit media playback controls, which supply their own dimming - no dimming layer is needed.
- **MAT-10** Both variants change appearance in response to system settings: a person's preferred Liquid Glass look, Reduce Transparency, and Increase Contrast. Design so the component still works in all of those states.

### 2.3 Colour on Liquid Glass

- **MAT-11** By default Liquid Glass **has no inherent colour** - it takes colour from the content directly behind it.
- **MAT-12** You may tint some Liquid Glass elements, giving them the look of coloured or stained glass. This is how the system styles prominent buttons.
- **MAT-13** On **small** elements (toolbars, tab bars) the system adapts the glass between light and dark in response to underlying content, and symbols/text default to **monochrome** - darker over light content, lighter over dark.
- **MAT-14** On **large** elements (sidebars) Liquid Glass appears **more opaque**, to preserve legibility over complex backgrounds and support richer content on the surface.
- **MAT-15** **Apply colour sparingly.** Reserve it for elements that genuinely benefit from emphasis - status indicators, primary actions.
- **MAT-16** To emphasise a primary action, **apply colour to the background, not to the symbol or text.** (This is what the system does with a Done button, using the app accent colour on the background.)
- **MAT-17** **NEVER add colour to the background of multiple controls** in the same context.
- **MAT-18** If the app has a colourful background or visually rich content, prefer a **monochromatic** appearance for toolbars and tab bars, or pick an accent colour with clear visual differentiation. In apps with mostly monochromatic content, using your brand colour as the app accent colour is an effective way to express identity.
- **MAT-19** Avoid overlapping similar colours between the content layer and the controls. Check the **resting state** - the top of a scroll view - for legibility, even if colourful content will intermittently scroll underneath.

### 2.4 Standard materials (the content layer's toolkit)

- **MAT-20** Use standard materials and effects - blur, vibrancy, blending modes - to convey structure *within* the content beneath Liquid Glass.
- **MAT-21** **Choose a material by semantic meaning and recommended usage, never by the colour it happens to impart.** System settings change how materials look and behave.
- **MAT-22** Always use **system-defined vibrant colours** on top of materials. Then you don't have to worry about colours reading too dark, bright, saturated or low-contrast in different contexts.
- **MAT-23** Thicker (more opaque) materials give better contrast for text and fine features. Thinner (more translucent) materials help people retain context by reminding them what's behind.
- **MAT-24 (iOS, iPadOS)** Four standard materials exist for the content layer: **ultra-thin, thin, regular (default), thick.**
- **MAT-25 (iOS, iPadOS)** Vibrancy levels for labels: `label` (default, highest contrast), `secondaryLabel`, `tertiaryLabel`, `quaternaryLabel` (lowest). Fills: `fill` (default), `secondaryFill`, `tertiaryFill`. Separators have a single level.
- **MAT-26 (iOS, iPadOS)** **Avoid quaternary label vibrancy on thin and ultraThin materials** - the contrast is too low.
- **MAT-27 (macOS)** macOS supplies vibrant versions of all system colours and two background blending modes - **behind window** and **within window**. Pick the one that complements your design, and test in a variety of contexts to find where vibrancy actually helps.

### 2.5 Motion of the material

- **MAT-28** Liquid Glass responds differently to different inputs: greater emphasis on **direct touch**, a more subdued effect for **trackpad** interaction. If you build custom glass, respect that difference rather than applying one motion everywhere.

---

## 3. Platform character - what each platform actually is

Apple frames each platform by display, ergonomics, inputs, interaction length and system features. Design decisions follow from these.

### 3.1 iOS (iPhone)

- Medium-size, high-resolution display. Held in one or both hands; switches orientation freely; viewing distance a foot or two.
- Inputs: Multi-Touch gestures, virtual keyboards, voice. Often personal data, gyroscope and accelerometer.
- Sessions swing between one or two minutes and an hour or more. Multiple apps open; frequent switching.

Rules:
- **IOS-1** Limit the number of on-screen controls; make secondary details and actions discoverable with minimal interaction.
- **IOS-2** Adapt seamlessly to appearance changes - device orientation, Dark Mode, Dynamic Type - so people can pick the configuration that works for them.
- **IOS-3** Support interactions that match how people hold the device. **Controls in the middle or bottom area of the display are easier and more comfortable to reach.** In particular, let people swipe to navigate back and swipe to initiate actions in a list row.
- **IOS-4** With permission, integrate platform capabilities so people don't have to type data - payments, biometric authentication, location.
- **IOS-5** System features to integrate with: widgets, Home Screen quick actions, Spotlight, Shortcuts, activity views.

### 3.2 iPadOS

- Large, high-resolution display. Held, set on a surface, or on a stand - so viewing distance varies, typically within about 3 feet.
- Inputs: Multi-Touch and virtual keyboards, attached keyboard or pointing device, Apple Pencil, voice - **and people often combine several input modes at once.**
- Sessions range from quick actions to hours of immersion. Multiple apps on screen at once is expected, as is drag and drop between them.

Rules:
- **IPAD-1** Use the large display to elevate content: minimise modal interfaces and full-screen transitions.
- **IPAD-2** Position controls where they're easy to reach but not in the way.
- **IPAD-3** **Use viewing distance and input mode to determine the size and density of on-screen content.**
- **IPAD-4** Support Multi-Touch gestures, physical keyboard/trackpad, and Apple Pencil. Consider interactions that combine input modes.
- **IPAD-5** Adapt to orientation, multitasking modes, Dark Mode and Dynamic Type - and transition effortlessly to running in macOS.
- **IPAD-6** System features to integrate with: multitasking, widgets, drag and drop.

### 3.3 macOS

- Typically large, high-resolution, often multiple displays (including iPad as an extra display). Stationary use, viewing distance roughly 1 to 3 feet.
- Inputs: any combination of physical keyboard, pointing devices, game controls, Siri.
- Sessions from a few minutes to several hours of deep concentration. Many apps open; smooth transitions between active and inactive states expected.

Rules:
- **MAC-1** Present more content in fewer nested levels and with less modality - while keeping a comfortable information density that doesn't make people strain.
- **MAC-2** Let people resize, hide, show and move windows. Support full-screen mode for a distraction-free context.
- **MAC-3** **Use the menu bar to give access to all the commands people need.** Everything the app can do should be reachable there.
- **MAC-4** Support high-precision input for pixel-perfect selections and edits.
- **MAC-5** Handle keyboard shortcuts so people can accelerate actions and work keyboard-only.
- **MAC-6** Support personalisation: customisable toolbars, windows configured to show the views people use most, chosen colours and fonts.
- **MAC-7** System features to integrate with: the menu bar, file management, full screen, Dock menus.

---

## 4. Foundations

### 4.1 Layout

**Visual hierarchy**
- **LAY-1** Order content by relative importance. People read top-to-bottom, leading-to-trailing - put the most important items near the **top and leading** side.
- **LAY-2** Prefer standard system components so UI can adapt automatically to right-to-left reading order.
- **LAY-3** Align elements so they're easy to scan; use **indentation** to convey hierarchy. People assume aligned items are related and indented items are subordinate to the item above.
- **LAY-4** Group related items using negative space, container shapes, or separator lines, so it's clear which elements are related and which aren't.
- **LAY-5** Use **progressive disclosure** - disclosure triangles, menus, nested views, scrollable sections - to reduce what's shown initially. Too much content and too many choices makes information harder to find and choices harder to understand.
- **LAY-6** **Differentiate controls from content.** Use Liquid Glass to give controls a distinct appearance.
- **LAY-7** **NEVER apply a solid or semi-opaque background colour beneath controls** to separate them from content. Use a **scroll edge effect** to visually elevate controls above content instead.
- **LAY-8** For full-screen background content, **extend it underneath sidebars, toolbars and tab bars** to fill the entire screen or window.
- **LAY-9** If scaling a background image to the full window edge means sidebars or inspectors cover important parts of it, use the **background extension effect**, which flips and blurs the image and mirrors it beneath the adjacent component. **[27]**

**Adaptability**
- **LAY-10** Apps must adapt to: regular/compact horizontal and vertical size classes; different screen sizes; different orientations and aspect ratios; system features such as the Dynamic Island; external displays, Display Zoom and resizable windows on iPad and Mac; text-size changes; locale-based internationalisation (LTR/RTL, date/time/number formatting, font variation, text length).
- **LAY-11** Respect system-defined safe areas, margins and guides, and use layout modifiers to fine-tune placement.
- **LAY-12** **Even an orientation-locked app must resize well.** A landscape-only game still needs to work across device and window sizes.
- **LAY-13** Be ready for text-size changes: horizontally adjacent views may need to stack vertically; containers may need to grow in height; single-line rows may need to become multi-line.
- **LAY-14** Preview on multiple devices, size classes, localisations and text sizes. Test the **largest and smallest layouts first** - that's where clipping shows up.
- **LAY-15** When background artwork would be cropped, letterboxed or pillarboxed in a different aspect ratio, **don't change its aspect ratio - scale it so it fills the screen completely.** Windows can be very wide and short or tall and narrow, so background art often needs to extend well beyond what a standard aspect ratio shows.

**Size classes (iOS, iPadOS)**
- **LAY-16** Each dimension is either **compact** or **regular**. Horizontal size class = narrow (compact) or wide (regular). Vertical size class = short (compact) or tall (regular).
- **LAY-17** The system sets size classes from device type, window configuration and multitasking state. iOS and iPadOS apps can exist in **every combination**.
- **LAY-18** **Determine layout from size classes, not device type or orientation.** A device's orientation and idiom don't tell you how much space is available.
- **LAY-19** Consider all possible combinations in both portrait and landscape aspect ratios. A layout designed only for iPhone landscape (regular width, compact height) will waste the vertical space available when someone resizes to regular height on iPad - and vice versa.
- **LAY-20** **Keep functionality the same as size classes change.** You may change how much functionality is *visible* - for example switching a tab bar to a sidebar, or surfacing actions that were in an overflow menu - but never change what the app can do.
- **LAY-21** Keep the layout recognisable and familiar to the platform when resizing. The app's idiom doesn't change just because its size class did.

**Guides and safe areas**
- **LAY-22** A **layout guide** is a rectangular region for positioning, aligning and spacing content. The system provides guides for standard margins and for restricting text width to a readable measure. You can define custom guides.
- **LAY-23** A **safe area** is the region of a window not covered by a hardware feature or another view (toolbar, tab bar, status bar). **Respecting the safe area is essential** so system UI and hardware features like the Dynamic Island don't obstruct content and controls.

**macOS layout**
- **LAY-24 (macOS)** **NEVER place controls or critical information at the bottom of a window.** People often move windows so the bottom edge falls below the bottom of the screen.
- **LAY-25 (macOS)** **Avoid displaying content behind the camera housing** at the top edge of the window.

---

### 4.2 Typography

**Legibility**
- **TYP-1** Use font sizes most people can read easily. Follow the per-platform default and minimum sizes - **for custom fonts as well as system fonts**:

| Platform | Default size | Minimum size |
|---|---|---|
| iOS, iPadOS | **17 pt** | **11 pt** |
| macOS | **13 pt** | **10 pt** |

- **TYP-2** Font weight affects readability. **If you use a custom font with a thin weight, aim larger than the recommended sizes.**
- **TYP-3** Test legibility in different contexts. If text is hard to read, increase type size, increase contrast by changing text or background colours, or switch to a typeface designed for legibility (the system fonts).
- **TYP-4** **In general, avoid light font weights.** Prefer **Regular, Medium, Semibold, Bold**. Avoid **Ultralight, Thin, Light** - they're hard to see, especially at small sizes.

**Hierarchy**
- **TYP-5** Adjust weight, size and colour to emphasise important information. **Maintain the relative hierarchy and visual distinction between text elements when people change text size.**
- **TYP-6** **Minimise the number of typefaces**, even in a highly customised interface. Mixing too many obscures hierarchy, hurts readability, and makes an interface feel internally inconsistent or poorly designed.
- **TYP-7** Prioritise important content when text size changes. Not everything should grow - when someone enlarges text to read content in a tabbed window, they don't expect the **tab titles** to grow too.

**System fonts**
- **TYP-8** Two families: **San Francisco (SF)** - sans serif, variants SF Pro, SF Compact, SF Arabic, SF Armenian, SF Georgian, SF Hebrew, SF Mono, plus **rounded** variants - and **New York (NY)**, a serif family designed to work alone and alongside SF.
- **TYP-9** SF Pro is the system font on iOS, iPadOS **and** macOS. iOS/iPadOS apps can also use NY. NY is available on Mac via Mac Catalyst.
- **TYP-10** System fonts ship in **variable** font format and support **dynamic optical sizes** - the system interpolates each glyph for the exact point size. You don't need discrete optical sizes (Text, Display) unless your design tool doesn't support the variable font format.
- **TYP-11** Weights run **Ultralight to Black**; SF also offers widths including **Condensed** and **Expanded**. SF Symbols use equivalent weights, so symbols and adjacent text weight-match precisely at any size.
- **TYP-12** **Use the built-in text styles.** A text style specifies a combination of weight, point size and leading. Using them with system fonts guarantees Dynamic Type and larger accessibility size support.
- **TYP-13** Modify built-in styles with **symbolic traits** when needed - e.g. the bold trait to create another level of hierarchy, or leading adjustments.
- **TYP-14** **Loose leading** (more space between lines) for wide columns or long passages, so people keep their place moving between lines. **Tight leading** where height is constrained, such as a list row. **NEVER use tight leading for three or more lines of text**, even where height is limited.
- **TYP-15** **NEVER embed system fonts in your app.** Access them through the system APIs.
- **TYP-16** In a running app the system font adjusts tracking dynamically at every point size. For accurate interface mockups you may need to adjust tracking manually (Apple publishes full tracking tables per size for SF Pro, SF Pro Rounded and New York).

**Custom fonts**
- **TYP-17** Custom fonts must be legible at various viewing distances and conditions, and must respect the recommended minimum sizes.
- **TYP-18** **Custom fonts must implement the same accessibility behaviours as system fonts** - Dynamic Type support and response to Bold Text.

**Dynamic Type (iOS, iPadOS)**
- **TYP-19** Dynamic Type is a system-level setting. **macOS does not support Dynamic Type.**
- **TYP-20** Verify the design scales and that text and glyphs are legible at all font sizes. Turn on Settings → Accessibility → Display & Text Size → Larger Text and confirm the app is still comfortably readable.
- **TYP-21** **Increase the size of meaningful interface icons as font size increases.** SF Symbols do this automatically.
- **TYP-22** **Keep truncation to a minimum as font size increases.** Aim to display as much useful text at the largest accessibility size as at the largest standard size. Avoid truncating text in scrollable regions unless people can open a separate view to read the rest. Configure labels to use as many lines as needed.
- **TYP-23** Consider adjusting layout at large sizes: switch to a **stacked layout** where text sits above secondary items, and **reduce the number of columns** as font size grows.
- **TYP-24** **Maintain a consistent information hierarchy regardless of font size** - keep primary elements toward the top of a view even when text is very large, so people don't lose track of them.

**The canonical iOS / iPadOS type scale - Large (default)**

| Style | Weight | Size (pt) | Leading (pt) | Emphasized weight |
|---|---|---|---|---|
| Large Title | Regular | 34 | 41 | Bold |
| Title 1 | Regular | 28 | 34 | Bold |
| Title 2 | Regular | 22 | 28 | Bold |
| Title 3 | Regular | 20 | 25 | Semibold |
| Headline | Semibold | 17 | 22 | Semibold |
| Body | Regular | 17 | 22 | Semibold |
| Callout | Regular | 16 | 21 | Semibold |
| Subhead | Regular | 15 | 20 | Semibold |
| Footnote | Regular | 13 | 18 | Semibold |
| Caption 1 | Regular | 12 | 16 | Semibold |
| Caption 2 | Regular | 11 | 13 | Semibold |

Point sizes are based on 144 ppi for @2x and 216 ppi for @3x designs. Emphasized weights were added to the specifications on 16 December 2025.

**The smaller and larger standard steps (iOS, iPadOS)**

| Style | xSmall | Small | Medium | **Large** | xLarge | xxLarge | xxxLarge |
|---|---|---|---|---|---|---|---|
| Large Title | 31 | 32 | 33 | **34** | 36 | 38 | 40 |
| Title 1 | 25 | 26 | 27 | **28** | 30 | 32 | 34 |
| Title 2 | 19 | 20 | 21 | **22** | 24 | 26 | 28 |
| Title 3 | 17 | 18 | 19 | **20** | 22 | 24 | 26 |
| Headline | 14 | 15 | 16 | **17** | 19 | 21 | 23 |
| Body | 14 | 15 | 16 | **17** | 19 | 21 | 23 |
| Callout | 13 | 14 | 15 | **16** | 18 | 20 | 22 |
| Subhead | 12 | 13 | 14 | **15** | 17 | 19 | 21 |
| Footnote | 12 | 12 | 12 | **13** | 15 | 17 | 19 |
| Caption 1 | 11 | 11 | 11 | **12** | 14 | 16 | 18 |
| Caption 2 | 11 | 11 | 11 | **11** | 13 | 15 | 17 |

**The five larger accessibility sizes (iOS, iPadOS)** - note how far they go. Body runs 28 → 33 → 40 → 47 → 53 pt.

| Style | AX1 | AX2 | AX3 | AX4 | AX5 |
|---|---|---|---|---|---|
| Large Title | 44 | 48 | 52 | 56 | 60 |
| Title 1 | 38 | 43 | 48 | 53 | 58 |
| Title 2 | 34 | 39 | 44 | 50 | 56 |
| Title 3 | 31 | 37 | 43 | 49 | 55 |
| Headline | 28 | 33 | 40 | 47 | 53 |
| Body | 28 | 33 | 40 | 47 | 53 |
| Callout | 26 | 32 | 38 | 44 | 51 |
| Subhead | 25 | 30 | 36 | 42 | 49 |
| Footnote | 23 | 27 | 33 | 38 | 44 |
| Caption 1 | 22 | 26 | 32 | 37 | 43 |
| Caption 2 | 20 | 24 | 29 | 34 | 40 |

**macOS built-in text styles** (macOS has no Dynamic Type, so this is the whole scale)

| Text style | Weight | Size (pt) | Line height (pt) | Emphasized weight |
|---|---|---|---|---|
| Large Title | Regular | 26 | 32 | Bold |
| Title 1 | Regular | 22 | 26 | Bold |
| Title 2 | Regular | 17 | 22 | Bold |
| Title 3 | Regular | 15 | 20 | Semibold |
| Headline | Bold | 13 | 16 | Heavy |
| Body | Regular | 13 | 16 | Semibold |
| Callout | Regular | 12 | 15 | Semibold |
| Subheadline | Regular | 11 | 14 | Semibold |
| Footnote | Regular | 10 | 13 | Semibold |
| Caption 1 | Regular | 10 | 13 | Medium |
| Caption 2 | Medium | 10 | 13 | Semibold |

- **TYP-25 (macOS)** Use the **dynamic system font variants** to match standard controls: control content, label, menu, menu bar, message, palette, title bar, tool tips, document text (user), monospaced document text, bold system, system.

---

### 4.3 Colour

**Best practices**
- **COL-1** **NEVER use the same colour to mean different things.** If your brand colour signals that a borderless button is interactive, using the same or a similar colour on non-interactive text is confusing.
- **COL-2** All colours must work in **light, dark and increased-contrast** contexts. With Increase Contrast on, colour differences become far more apparent.
- **COL-3** If you define a custom colour, supply **light and dark variants, plus an increased-contrast option for each variant** that provides significantly higher visual differentiation.
- **COL-4** **Even if your app ships in a single appearance mode, provide both light and dark colours** - Liquid Glass adaptivity needs them. **[27]**
- **COL-5** Test the colour scheme under a variety of lighting conditions. In bright surroundings colours look darker and more muted; in dark environments they appear brighter and more saturated.
- **COL-6** Test on different devices. True Tone adjusts display white point to ambient light. On Mac, test with different colour profiles (P3, sRGB) via System Settings → Displays.
- **COL-7** Consider how artwork and translucency affect nearby colours. Variations in artwork sometimes warrant changing nearby colours to keep continuity and stop interface elements becoming overpowering or underwhelming. Colours also look different behind or on a translucent element.
- **COL-8** If people can choose colours, **prefer the system colour picker** - consistent experience, and a saved colour set available from any app.

**Inclusive colour**
- **COL-9** **NEVER rely solely on colour** to differentiate objects, indicate interactivity, or communicate essential information. Always provide the same information another way - text labels, glyph shapes.
- **COL-10** Avoid colours that make content hard to perceive. Insufficient contrast makes icons and text blend into the background.
- **COL-11** Consider how colours are perceived in other countries and cultures. Red means danger in some cultures and carries positive connotations in others. In some places white is associated with death or grief, elsewhere with purity or peace. **If colour communicates meaning, verify the meaning holds in every locale you ship.**

**System colours**
- **COL-12** **NEVER hard-code system colour values.** Published values are for design reference only; actual values fluctuate release to release based on environmental variables. Use the APIs.
- **COL-13** **Dynamic system colours** are defined **semantically by purpose**, not appearance, and adapt automatically to light and dark.
- **COL-14** **NEVER redefine the semantic meaning of a dynamic system colour.** Don't use `separator` as a text colour, or `secondaryLabel` as a background colour.
- **COL-15 (iOS, iPadOS)** Two sets of dynamic background colours - **system** and **grouped** - each with primary, secondary and tertiary variants. Use the **grouped** set with a grouped table view, the **system** set otherwise. Hierarchy: primary for the overall view, secondary for grouping content within it, tertiary for grouping within secondary.
- **COL-16 (iOS, iPadOS)** Foreground dynamic colours: `label`, `secondaryLabel`, `tertiaryLabel`, `quaternaryLabel`, `placeholderText`, `separator` (lets underlying content show through), `opaqueSeparator` (doesn't), `link`.
- **COL-17 (iOS, iPadOS)** System grays run `systemGray` through `systemGray6` (SwiftUI's `gray` is `systemGray`).
- **COL-18** The twelve system colours: **red, orange, yellow, green, mint, teal, cyan, blue, indigo, purple, pink, brown** - each with default light, default dark, increased-contrast light and increased-contrast dark values.
- **COL-19 (macOS)** macOS defines a large set of semantic colours (label/secondary/tertiary/quaternary label, control, control background, control text, unavailable control text, selected content background, selected control, selected text, selected text background, unemphasized variants for non-key windows, separator, grid, header text, highlight, shadow, keyboard focus indicator, find highlight, link, placeholder text, text, text background, under page background, window background, window frame text, alternating content backgrounds, control accent, current control tint).
- **COL-20 (macOS)** You can specify an **app accent colour** that customises buttons, selection highlighting and sidebar icons - applied when the person's Accent color setting is **multicolor**. If they choose a specific accent colour, the system overrides yours. The exception: a sidebar icon using a **fixed** colour you specify is never overridden, because its colour carries meaning.

**Colour management**
- **COL-21** Apply a colour profile to every image. sRGB produces accurate colours on most displays.
- **COL-22** Use **wide colour (Display P3, 16 bits per channel, exported as PNG)** to enhance photos, video and status indicators on compatible displays. You need a wide-colour display to design P3 images and select P3 colours.
- **COL-23** Provide colour-space-specific variants when needed. Two very similar P3 colours can be hard to distinguish on sRGB; P3 gradients can appear clipped on sRGB. Supply different versions per colour space in the asset catalog.

---

### 4.4 Dark Mode

- **DRK-1** Dark Mode is a **systemwide** setting on iOS, iPadOS, macOS and tvOS. **Many people use it as their default and expect every app to respect it.**
- **DRK-2** **NEVER offer an app-specific appearance setting.** It creates extra work (people must change more than one setting) and makes the app look broken when it ignores the systemwide choice.
- **DRK-3** The app must look good in **both** modes, because people can also choose **Auto**, which switches during the day - potentially while your app is running.
- **DRK-4** Test with **Increase Contrast and Reduce Transparency** on, separately and together. In Dark Mode, Increase Contrast can *reduce* the visual contrast between dark text and a dark background. Text that people with strong vision can still read may be illegible for many.
- **DRK-5** Using **only** a dark appearance is acceptable in rare cases - e.g. an app built around immersive media viewing, where the UI should recede.
- **DRK-6** Dark Mode colours are **not** simply inversions of their light counterparts. Many are inverted; some are not.
- **DRK-7** Use semantic colours that adapt automatically. For custom colours, add a **Color Set** asset with bright and dim variants. **NEVER use hard-coded colour values or colours that don't adapt.**
- **DRK-8** **Minimum contrast ratio between colours: 4.5:1.** For custom foreground and background colours, **strive for 7:1, especially in small text.**
- **DRK-9** **Soften white backgrounds.** If a content image has a white background, darken it slightly so it doesn't glow against the surrounding dark UI.
- **DRK-10** Use SF Symbols wherever possible - they adapt automatically.
- **DRK-11** Design separate light and dark interface icons where necessary. An icon of a full moon may need a subtle dark outline against a light background and none against dark.
- **DRK-12** Use the same full-colour asset if it looks good in both modes; otherwise modify it or create separate light and dark assets, combined into a single named image via the asset catalog.
- **DRK-13** Use the system label colours (primary, secondary, tertiary, quaternary) - they adapt automatically.
- **DRK-14** **Use system views to draw text fields and text views** rather than drawing text yourself; they adjust for the presence or absence of vibrancy.
- **DRK-15 (iOS, iPadOS)** Dark Mode uses **two** sets of background colours: **base** (dimmer, background interfaces recede) and **elevated** (brighter, foreground interfaces advance). The system switches base → elevated automatically for popovers and modal sheets, and uses elevated to separate apps in multitasking and windows in multi-window contexts. **Prefer system background colours** - a custom background makes these system-provided distinctions harder to perceive.
- **DRK-16 (macOS)** With the **graphite** accent colour, window backgrounds pick up colour from the desktop picture - **desktop tinting**. Include some transparency in custom component backgrounds so they participate, but **only** on components that have a visible background or bezel, and **only** in a neutral state. Don't add transparency to a component in a coloured state, or its colour will fluctuate as the window moves across the desktop or the picture changes.

---

### 4.5 Interface icons (glyphs)

- **ICO-1** An interface icon expresses **a single concept** in a way people instantly understand, using streamlined shapes and touches of colour. (App icons are different - they can use rich shading, texturing and highlighting.)
- **ICO-2** Create a **recognisable, highly simplified** design. Too many details make an icon confusing or unreadable. Use familiar visual metaphors directly related to the action or content.
- **ICO-3** **All interface icons in the app must use a consistent size, level of detail, stroke thickness and perspective** - whether custom, system, or mixed. Adjust an icon's dimensions where needed so it looks visually consistent with its neighbours.
- **ICO-4** **Match the weight of an icon to adjacent text**, unless you specifically want to emphasise one over the other.
- **ICO-5** **Optically centre, don't geometrically centre.** Asymmetric icons look unbalanced when geometrically centred; add padding to the asset so geometric centring produces optical centring. The adjustments are typically very small and have a big impact.
- **ICO-6** Don't provide selected/unselected variants for icons used in standard components (toolbars, tab bars, buttons) - the system updates the selected appearance automatically.
- **ICO-7** Use **inclusive images**: prefer gender-neutral human figures; avoid images that are hard to recognise across cultures or languages.
- **ICO-8** Include text in an icon **only when it's essential** for conveying meaning. Localise any individual characters. For a passage of text, design an abstract representation and provide a flipped version for RTL.
- **ICO-9** Use a **vector format (PDF or SVG)** for custom interface icons - the system scales them for high-resolution displays. PNG doesn't scale, so it needs multiple versions. Alternatively make a custom SF Symbol and specify a scale that matches adjacent text.
- **ICO-10** **Provide alternative text labels (accessibility descriptions) for every custom interface icon.**
- **ICO-11** **NEVER use replicas of Apple hardware products.** Hardware designs change and date your icons. If you must show Apple hardware, use only images from Apple Design Resources or the SF Symbols that represent Apple products.

**Apple's standard action icons** - use these symbol names rather than inventing your own:

| Action | Symbol | Action | Symbol |
|---|---|---|---|
| Cut | `scissors` | Search | `magnifyingglass` |
| Copy | `document.on.document` | Find | `text.page.badge.magnifyingglass` |
| Paste | `document.on.clipboard` | Filter | `line.3.horizontal.decrease` |
| Done | `checkmark` | Share | `square.and.arrow.up` |
| Cancel / Deselect | `xmark` | Print | `printer` |
| Delete | `trash` | Account | `person.crop.circle` |
| Undo | `arrow.uturn.backward` | Like | `hand.thumbsup` |
| Redo | `arrow.uturn.forward` | Dislike | `hand.thumbsdown` |
| Compose | `square.and.pencil` | Bring to Front | `square.3.layers.3d.top.filled` |
| Duplicate | `plus.square.on.square` | Send to Back | `square.3.layers.3d.bottom.filled` |
| Rename | `pencil` | Bring Forward | `square.2.layers.3d.top.filled` |
| Move to / Folder | `folder` | Send Backward | `square.2.layers.3d.bottom.filled` |
| Attach | `paperclip` | Select | `checkmark.circle` |
| Add | `plus` | Alarm | `alarm` |
| More | `ellipsis` | Archive | `archivebox` |
| Bold / Italic / Underline | `bold` / `italic` / `underline` | Calendar | `calendar` |
| Superscript / Subscript | `textformat.superscript` / `textformat.subscript` | | |
| Align left / centre / justify / right | `text.alignleft` / `text.aligncenter` / `text.justify` / `text.alignright` | | |

**macOS document icons**
- **ICO-12 (macOS)** A document icon looks like a piece of paper with the top-right corner folded down. If you don't supply one, macOS composites your app icon and the file extension onto the canvas.
- **ICO-13 (macOS)** Design simple images with uncomplicated shapes and a reduced palette - a document icon can display as small as **16×16 px**.
- **ICO-14 (macOS)** Reduce complexity in small versions: fewer, thicker lines aligned to the reduced pixel grid; at 16×16 px consider removing detail lines altogether.
- **ICO-15 (macOS)** **Keep important content out of the top-right corner** of the background fill - the system masks it and draws the white folded corner on top.
- **ICO-16 (macOS)** Background fill sizes: 512×512 @1x / 1024×1024 @2x; 256 / 512; 128 / 256; 32 / 64; 16 / 32 px.
- **ICO-17 (macOS)** Centre image sizes: 256 / 512; 128 / 256; 32 / 64; 16 / 32 px. **The centre image measures half the size of the overall canvas** (a 32×32 px document icon uses a 16×16 px centre image).
- **ICO-18 (macOS)** Define a margin of about **10% of the image canvas** and keep most of the image inside it - the image should occupy about **80%** of the canvas. (In a 256×256 px canvas, most of the image fits within 205×205 px.)
- **ICO-19 (macOS)** You may supply a short descriptive term instead of the file extension (SceneKit uses "scene" rather than "scn"). The system scales the text to fit and capitalises every letter by default, so keep it short enough to stay legible at small sizes.

---

### 4.6 App icons

**Layers**
- **AIC-1** A layered app icon gives you the most control. On iOS, iPadOS, macOS and watchOS it has a **background layer plus one or more foreground layers**, and takes on Liquid Glass attributes - **specular highlights, refraction, translucency** - that adapt with icon size, apply consistently across platforms, and can look different between system versions. **[27]**
- **AIC-2** Craft foreground layers in your design tool, then import them into **Icon Composer** (included with Xcode) where you define the background, adjust placement, apply visual effects, annotate default/dark/mono variants, preview across system versions, and export.
- **AIC-3** **Prefer clearly defined edges in foreground layers.** Avoid soft and feathered edges - system-drawn highlights and shadows depend on crisp edges.
- **AIC-4** **Vary opacity across foreground layers** to increase depth and liveliness. Import fully opaque layers and adjust transparency inside Icon Composer so you can preview how transparency and system effects interact.
- **AIC-5** Design a background that both stands out and emphasises the foreground. Icon Composer supports solid colours and gradients, so importing a custom background image is usually unnecessary; if you do import one, make it **full-bleed and opaque**. Ensure gradients respond well to system lighting effects.
- **AIC-6** **Prefer vector graphics (SVG, PDF).** Outline your artwork and convert text to outlines. Use PNG only for mesh gradients and raster artwork.

**Shape**
- **AIC-7** On iOS, iPadOS and macOS icons are **square**; the system masks them into rounded corners that precisely match the curvature of other rounded interface elements and of the device bezel itself.
- **AIC-8** **Provide unmasked square layers** and let the system apply the shape. **NEVER pre-mask your layers** - it degrades specular highlights and makes edges look jagged.
- **AIC-9** **Keep primary content centred** so it isn't truncated when the system adjusts corners or applies masking. Use the grids in Apple's app icon production templates.

**Design**
- **AIC-10** Embrace simplicity. An icon with fine visual features looks busy once system shadows and highlights are applied, and details vanish at small sizes. Find one concept, express it with a **minimal number of shapes**.
- **AIC-11** Prefer a **simple background** - solid colour or gradient. **You don't need to fill the entire canvas with content.**
- **AIC-12** Keep the icon design **visually consistent across every platform** you support, so people find your app quickly and don't mistake it for several different apps.
- **AIC-13** Consider basing the design on **filled, overlapping shapes**; overlapping solids plus transparency and blurring create depth.
- **AIC-14** Include text **only if it's essential** to the experience or brand. Text doesn't support accessibility or localisation, is usually too small to read, and clutters the icon. Your app name already appears nearby. A single mnemonic letter can help; **NEVER include words like "Watch", "Play", "New", or "For visionOS".**
- **AIC-15** **Prefer illustrations to photos.** Photos are full of detail that breaks down across appearances, at small sizes, and when split into layers.
- **AIC-16** **NEVER replicate standard UI components or use app screenshots** in your icon.
- **AIC-17** Avoid extremely thin line weights and sharp corners - they lose detail and crispness at small sizes and lower resolutions.
- **AIC-18** **NEVER use replicas of Apple hardware products** - they're copyrighted and can't be reproduced in app icons.

**Visual effects**
- **AIC-19** **Let the system handle blurring and other visual effects.** Don't bake in specular highlights, inter-layer drop shadows, beveled edges, blurs or glows. Custom effects interfere with system effects and are static where the system's are dynamic.
- **AIC-20** If you do include custom effects, use them intentionally and test in Icon Composer, on a simulated device in Device Hub, and on hardware.
- **AIC-21** Group layers in Icon Composer or your design tool to apply effects at group level. Groups get additional Liquid Glass customisation - specular highlights, refraction, translucency.

**Appearances**
- **AIC-22** On iOS, iPadOS and macOS people choose **default, dark, clear, or tinted** Home Screen icons. You can design a variant for each; the system generates any you don't supply. **[27]**
- **AIC-23** **Keep the icon's core visual features the same across all appearances.** Don't swap elements in and out per variant - it makes your app harder to find when someone changes appearance.
- **AIC-24** Dark icons are more subdued; clear and tinted more so still. A great icon is visible, legible and recognisable in every variant.
- **AIC-25** Use the light icon as the basis for the dark one. Choose complementary colours, avoid excessively bright images. **Colour backgrounds generally offer the greatest contrast in dark icons.**
- **AIC-26** Alternate app icons are allowed (iOS, iPadOS, tvOS, and compatible apps in visionOS) via your app's settings. Each must stay closely related to your content, and none may be mistakable for another app. **Alternate icons on iOS and iPadOS require their own dark, clear and tinted variants**, and all variants are subject to App Review.

**Specification**

| Platform | Layout shape | Shape after masking | Layout size | Style | Appearances |
|---|---|---|---|---|---|
| iOS, iPadOS, macOS | Square | Rounded rectangle | **1024×1024 px** | Layered | Default, dark, clear light, clear dark, tinted light, tinted dark |

- **AIC-27** Supported colour spaces: **sRGB** (colour), **Gray Gamma 2.2** (grayscale), **Display P3** (wide gamut). The system scales your icon down for Settings, notifications and similar.

---

### 4.7 SF Symbols

- **SF-1** SF Symbols provides thousands of symbols that integrate with San Francisco, **automatically aligning with text in all weights and sizes.** Use them anywhere an interface icon can appear - toolbars, tab bars, context menus, inline in text.
- **SF-2** **Availability is versioned.** Symbols and symbol features introduced in a given year are not available on earlier OS versions. Check the minimum OS you support.
- **SF-3** **NEVER use SF Symbols - or images confusingly similar to them - in app icons, logos, or any other trademarked use.** This is a licence condition.
- **SF-4** **NEVER customise a symbol that depicts an Apple product or feature.** Those are copyrighted; the SF Symbols app badges them with an Info icon and the inspector describes the restriction. You may display them as-is.

**Rendering modes**
- **SF-5** Four modes: **Monochrome** (one colour, all layers), **Hierarchical** (one colour, opacity varied per hierarchical layer), **Palette** (two or more colours, one per layer - with only two colours supplied for a three-level symbol, secondary and tertiary share), **Multicolor** (intrinsic colours that carry meaning, e.g. green `leaf`, red `trash.slash`).
- **SF-6** Use **system-provided colours** whatever the rendering mode, so symbols adapt to accessibility accommodations, vibrancy and Dark Mode automatically.
- **SF-7** **Verify the rendering mode works in every context.** Size and background contrast change how discernible a symbol's details are. Automatic gives you the preferred mode, but check it.
- **SF-8** **Gradient rendering** (SF Symbols 7+) generates a smooth linear gradient from a single source colour, in all rendering modes, for system and custom colours and custom symbols. **It looks best at larger sizes.**

**Variable colour**
- **SF-9** Use **variable colour** to represent something that changes over time - capacity, strength, progress - by colouring layers as a value crosses thresholds between 0 and 100%.
- **SF-10** Layers that don't change with the value should opt out (the speaker body in `speaker.wave.3` doesn't get variable colour; only the wave layers do).
- **SF-11** **Use variable colour to communicate change, NEVER to communicate depth.** Depth and hierarchy are Hierarchical rendering mode's job.

**Weights and scales**
- **SF-12** Nine weights (ultralight → black) each corresponding to a San Francisco weight, for precise weight matching with adjacent text.
- **SF-13** Three scales - **small, medium (default), large** - defined relative to the cap height of San Francisco. Scale adjusts a symbol's emphasis against adjacent text **without** breaking weight matching at the same point size.

**Design variants**
- **SF-14** **Outline** is the most common variant - no solid areas, resembling text. Most symbols also have **fill**. There are also **slash** variants (item or action unavailable) and **enclosed** variants (circle, square, rectangle), and enclosed/slash often combine with outline/fill.
- **SF-15** Use **outline** in toolbars, lists, and anywhere a symbol sits alongside text. Use **enclosing shapes** to improve legibility at small sizes. Use **fill** for more visual emphasis - iOS tab bars, swipe actions, and where an accent colour communicates selection.
- **SF-16** Often the view decides for you: an **iOS tab bar prefers fill**, a **toolbar takes outline**. Don't override without reason.
- **SF-17** Language- and script-specific variants exist (Latin, Arabic, Hebrew, Hindi, Thai, Chinese, Japanese, Korean, Cyrillic, Devanagari, several Indic numeral systems) and **adapt automatically when the device language changes.**

**Animations**
- **SF-18** Available animations: **Appear, Disappear, Bounce, Scale, Pulse, Variable colour, Replace, Magic Replace, Wiggle, Breathe, Rotate, Draw On / Draw Off** (Draw On/Off is SF Symbols 7+). They work on every symbol in every rendering mode, weight and scale, and on custom symbols.
- **SF-19** What each one is for:
  - **Bounce** - plays once; communicates that an action occurred or needs to take place.
  - **Scale** - persists until you change or remove it; draws attention to a selected item or gives feedback on choice.
  - **Pulse** - varies opacity; communicates ongoing activity, played continuously until a condition is met.
  - **Breathe** - varies opacity *and* size; conveys status change or ongoing activity such as a recording session.
  - **Variable colour** - communicates progress or ongoing activity (playback, connecting, broadcasting). Cumulative (changes persist per layer until the cycle ends) or iterative (one layer at a time). Symbols are annotated **open loop** (start and end don't meet) or **closed loop** (they do); closed-loop symbols give seamless continuous playback.
  - **Replace** - swaps one symbol for another. Three configurations: **down-up** (state change), **up-up** (state change with forward progression), **off-up** (state change emphasising the next available state).
  - **Magic Replace** - the **new default** replace animation: a smart transition between two related symbols, where slashes draw on and off and badges appear or disappear. Falls back to down-up between unrelated symbols; you can pick a different fallback direction.
  - **Wiggle** - highlights a change or a call to action someone might overlook, or reinforces direction.
  - **Rotate** - acts as a visual indicator or imitates real-world behaviour; some symbols rotate entirely, others (a desk fan) use **By Layer** rotation so only the blades spin.
  - **Draw On / Draw Off** - draws along a path through guide points; all layers at once, staggered, or one at a time.
- **SF-20** **Apply animations judiciously.** There's no technical limit, but too many overwhelm an interface and distract people.
- **SF-21** Make sure each animation serves a clear purpose in communicating the symbol's intent, and consider how a combination might be read.
- **SF-22** Consider the app's tone. An animation should align with brand identity and overall style.

**Custom symbols**
- **SF-23** Export the template for a similar system symbol, then modify it in a vector editor. Use the template as a guide so the custom symbol matches system symbols in **level of detail, optical weight, alignment, position and perspective**. Strive for **simple, recognisable, inclusive, directly related** to the action or content.
- **SF-24** **Annotate** each layer with a colour or a hierarchical level (primary, secondary, tertiary) so rendering modes work.
- **SF-25** Assign **negative side margins** where a badge or other element increases width, to aid optical horizontal alignment. Use Apple's naming pattern, e.g. `left-margin-Regular-M`.
- **SF-26** To animate by layer, annotate the layers. **Z-order** determines the order colours apply for variable colour, and you can animate front-to-back or back-to-front, or by layer group so related layers move together.
- **SF-27** **Test every animation preset against your custom symbols** - shapes and paths often don't behave as expected in motion. **Draw whole shapes** rather than cutouts (draw the full person, plus an offset path annotated as an erase layer, rather than cutting a hole) so layer information survives for animation.
- **SF-28** **Don't hand-build common variants** - enclosures, badges. Use the SF Symbols app's component library so your variants stay consistent with the system set.
- **SF-29** Provide alternative text labels for custom symbols.

---

### 4.8 Images and resolution

- **IMG-1** A **point** is an abstract unit. On 2D platforms it maps to a varying number of pixels depending on display resolution.
- **IMG-2** Scale factors to provide: **iOS - @2x and @3x. iPadOS - @2x. macOS - @1x and @2x.**
- **IMG-3** Append `@1x`, `@2x`, `@3x` to filenames in the asset catalog.
- **IMG-4** **Design at the lowest resolution and scale up.** With resizable vector shapes, position control points at whole values so they align cleanly at 1x - and therefore stay aligned to the raster grid at 2x and 3x.
- **IMG-5** Formats:

| Image type | Format |
|---|---|
| Bitmap or raster work | De-interlaced PNG |
| PNG graphics not needing full 24-bit colour | 8-bit colour palette |
| Photos | JPEG (optimised) or HEIC |
| Flat icons, interface icons, flat artwork needing high-res scaling | PDF or SVG |

- **IMG-6** Include a colour profile with every image.
- **IMG-7** **Always test images on a range of actual devices.** An image that looks great at design time can appear pixelated, stretched or compressed on real hardware.

---

### 4.9 Motion

- **MOT-1** Many system components include motion automatically, and adjust it in response to accessibility settings and input method. Liquid Glass moves with more emphasis under direct touch and more subtly under a trackpad.
- **MOT-2** **Add motion purposefully.** Never add motion for the sake of motion. **Gratuitous or excessive animation distracts people and can make them feel disconnected or physically uncomfortable.**
- **MOT-3** **Make motion optional.** NEVER use motion as the only way to communicate important information. Supplement visual feedback with **haptics and audio**.
- **MOT-4** Strive for realistic feedback motion that follows people's gestures and expectations. If a view is revealed by sliding down from the top, people don't expect to dismiss it by sliding sideways.
- **MOT-5** **Aim for brevity and precision** in feedback animation. Brief, precise motion feels lightweight and often communicates better than prominent animation.
- **MOT-6** **Generally avoid adding motion to frequent UI interactions.** The system already provides subtle animation for standard elements; don't make people watch unnecessary motion every time they touch a custom control.
- **MOT-7** **Let people cancel motion.** Don't make people wait for an animation to finish before they can act, especially if they'll see it more than once.
- **MOT-8** Consider animated symbols (SF Symbols 5+) where they make sense.
- **MOT-9** For games: **maintain a consistent 30–60 fps**; use the device's graphics capabilities to set good defaults so people don't have to change settings first; let people customise the visual experience to optimise performance or battery life.

**Reduce Motion (from the Accessibility guidance, but it belongs here)**
- **MOT-10** When Reduce Motion is on: reduce automatic and repetitive animations including zooming, scaling and peripheral motion; **tighten animation springs to reduce bounce**; **track animations directly with people's gestures**; **avoid animating depth changes in z-axis layers**; **replace x-, y-, and z-axis transitions with fades**; **avoid animating into and out of blurs**.
- **MOT-11** Be cautious with fast-moving and blinking animation. In excess it distracts, causes dizziness, and in some cases triggers epileptic episodes.

---

### 4.10 Accessibility

An accessible interface is **intuitive** (familiar, consistent interactions), **perceivable** (doesn't rely on any single sense), and **adaptable** (supports system accessibility features and personalisation).

- **A11Y-1** Audit with **Accessibility Inspector** and run **accessibility testing** as part of your process.
- **A11Y-2** You can declare feature support on the App Store with **Accessibility Nutrition Labels** (managed in App Store Connect).

**Vision**
- **A11Y-3** Let people enlarge text by **at least 200%** (140% on watchOS), via Dynamic Type or custom UI.
- **A11Y-4** For custom type styles, follow the recommended default and minimum sizes (iOS/iPadOS 17 / 11 pt; macOS 13 / 10 pt). Thin custom weights need to be **larger** than the recommendation.
- **A11Y-5** **Minimum contrast ratios** - the values Accessibility Inspector uses, from WCAG Level AA:

| Text size | Text weight | Minimum contrast ratio |
|---|---|---|
| Up to 17 pt | All | **4.5:1** |
| 18 pt | All | **3:1** |
| All | Bold | **3:1** |

- **A11Y-6** If the app doesn't meet that by default, it **must** at least provide a higher-contrast colour scheme when Increase Contrast is on. Check both light and dark appearances.
- **A11Y-7** Prefer **system-defined colours** - they carry accessible variants that adapt to Increase Contrast and to light/dark automatically.
- **A11Y-8** **Convey information with more than colour alone.** Red-green and blue-orange pairings are particularly difficult. Offer distinct shapes or icons alongside colour. Consider letting people customise colour schemes (chart colours, game characters).
- **A11Y-9** Describe the interface and content for **VoiceOver**.
- **A11Y-10** Two contrast standards are in play: **WCAG** and the **Accessible Perceptual Contrast Algorithm (APCA)**. Use standard calculators.

**Hearing**
- **A11Y-11** **NEVER communicate dialogue or crucial information through audio alone.** Provide, as appropriate: **captions** (textual equivalent of audible information, synchronised live - game cutscenes, video clips), **subtitles** (live on-screen dialogue in the viewer's language - TV, film), **audio descriptions** (spoken narration of visual-only information, in natural pauses), **transcripts** (complete textual description of both audible and visual information - podcasts, audiobooks). Let people customise how that text is presented.
- **A11Y-12** **Pair audio cues with haptics** for people who can't perceive the audio or have sound off. On iOS and iPadOS, Music Haptics and Audio Graphs let people experience music and infographics through vibration and texture.
- **A11Y-13** **Augment audio cues with visual cues** - critical where important content may be off screen. If audio guides people toward an action, add a visual indicator pointing at it.

**Mobility**
- **A11Y-14** **Control sizes:**

| Platform | Default control size | Minimum control size |
|---|---|---|
| iOS, iPadOS | **44×44 pt** | **28×28 pt** |
| macOS | **28×28 pt** | **20×20 pt** |

- **A11Y-15** **Spacing between controls matters as much as size.** Roughly **12 pt of padding** around elements that include a bezel; roughly **24 pt of padding** around the visible edges of elements without a bezel.
- **A11Y-16** **Use the simplest gesture possible** for frequent interactions. **Avoid custom multi-finger and multi-hand gestures.**
- **A11Y-17** **Always offer an alternative to a gesture.** Core functionality must be reachable through more than one physical interaction - if a swipe dismisses a view, also provide a button.
- **A11Y-18** Support **Voice Control** by labelling interface elements properly.
- **A11Y-19** Integrate **Siri and Shortcuts** so tasks can be done by voice alone, and initiated from Siri, the Action button, the Home Screen, or Control Center.
- **A11Y-20** Test against **VoiceOver, AssistiveTouch, Full Keyboard Access, Pointer Control and Switch Control.**

**Speech**
- **A11Y-21** **People must be able to navigate and interact using the keyboard alone.** Evaluate the app with **Full Keyboard Access** on.
- **A11Y-22** **NEVER override system-defined keyboard shortcuts.**
- **A11Y-23** Support **Switch Control** - selecting, tapping, typing and drawing driven by external hardware, game controllers, or sounds like a click or a pop.

**Cognitive**
- **A11Y-24** Keep actions simple and intuitive. **Prefer system gestures and behaviours people already know over custom gestures they must learn and retain.**
- **A11Y-25** **Minimise time-boxed interface elements.** Views and controls that auto-dismiss on a timer are a problem for people who need longer to process information and for assistive technologies that take longer to traverse an interface. **Prefer dismissing views with an explicit action.**
- **A11Y-26** In games, consider difficulty accommodations - reduced completion criteria, adjusted reaction time, control assistance.
- **A11Y-27** **NEVER autoplay audio or video without also providing controls to start and stop it.** Make those controls discoverable and easy to act on, and consider a global opt-out.
- **A11Y-28** Respond appropriately to the **Dim Flashing Lights** setting if your app plays video.
- **A11Y-29** Respond to **Reduce Motion** (see MOT-10).
- **A11Y-30** Optimise for **Assistive Access** (iOS, iPadOS) - a streamlined version of your app with a default layout and control presentation. When it's on: identify the core functionality and remove non-critical workflows and UI; break multi-step workflows so people focus on **a single interaction per screen**; and **always ask for confirmation twice** for any action that's hard to recover from, such as deleting a file.

---

### 4.11 Inclusion

- **INC-1** Investigate people's goals and perspectives first. Perspectives arise from age, gender and gender identity, race and ethnicity, sexuality, physical attributes, cognitive attributes, permanent/temporary/situational disabilities, language and culture, religion, education, political or philosophical opinion, and social and economic context.
- **INC-2** **An inoffensive app isn't necessarily an inclusive one.** Don't frame the work as a search for content that might offend; focus on creating a welcoming experience everyone can enjoy.
- **INC-3** Consider the **tone** of your copy from different perspectives. An academic tone can make an app seem to welcome only high levels of education. Be clear, direct and respectful.
- **INC-4** Use **you** and **your** to address people directly. **Referring to people as "the user" or "the player" makes the experience feel distant and unwelcoming.** Reserve **we** and **our** for your software or company - otherwise they imply a personal relationship that can read as insulting or condescending.
- **INC-5** **Define specialised or technical terms before using them**, and make the definitions easy to look up. Plain language is easier to read *and* to translate.
- **INC-6** **Replace colloquial expressions with plain language.** They're culture-specific, hard to translate, and some carry exclusionary histories ("peanut gallery", "grandfathered in"). Even a harmless colloquialism excludes everyone who doesn't understand it.
- **INC-7** **Be very careful with humour.** It's subjective and hard to translate; it risks confusing, irritating on repeat encounters, and insulting people who read it differently.
- **INC-8** An approachable app requires no prior skills or knowledge and gives a clear path to deeper understanding. Present a clear, straightforward interface, and build in ways to learn - an onboarding flow that lets newcomers go step by step while others skip to the content.
- **INC-9** **Avoid unnecessary references to specific genders.** Rewrite "You can let a subscriber post his or her recipes" as "Subscribers can post recipes" - the gender-neutral plural also survives localisation into languages with gendered pronouns.
- **INC-10** Use **nongendered human images** for generic people, so "generic person" reads as "human" rather than "man" or "woman". SF Symbols provides nongendered figure and person symbols. Prefer giving people tools to customise avatars, emoji, glyphs and characters.
- **INC-11** **Most apps don't need to know a person's gender.** If you genuinely require it (health or legal reasons), offer inclusive options - **nonbinary, self-identify, decline to state** - and consider letting people specify pronouns.
- **INC-12** **Portray a range of human characteristics and activities** in copy and images: racial backgrounds, body types, ages, physical capabilities. **Avoid stereotypical representations** of occupations and behaviours - not only male doctors and female nurses; not heroes and villains that perpetuate racial or gender stereotypes.
- **INC-13** Review settings and objects. High affluence can read as unwelcoming and out of touch. Prefer places, homes, activities and items familiar and relatable to most people.
- **INC-14** **Audit your assumptions.** Apple's example: security questions like "What was your favourite subject in college?", "What was the make of your first car?", "How did you feel when you first saw a rainbow?" all assume experiences not everyone has. Universal alternatives: "What's your favourite activity?", "What was the name of your first friend?", "What quality describes you best?"
- **INC-15** Remember each disability is a **spectrum**, and that **everyone experiences disability** - permanent, temporary (short-term hearing loss from an infection) and situational (unable to hear on a noisy train).
- **INC-16** Include people with disabilities when you represent a variety of people. **NEVER use a disability to express a negative quality.**
- **INC-17** Take a **people-first** approach in writing about disability - describe accomplishments and goals before mentioning a disability. If writing about a specific person or community, find out how they self-identify.
- **INC-18** Internationalise first, then localise. Plain language, no unnecessary gender references, varied representation, and avoiding culture-specific content all make localisation easier. SF Symbols helps - many language-specific glyphs, plus glyphs that work in both LTR and RTL.
- **INC-19** Colour meanings are culture-specific. If colour communicates, verify it communicates the **same** thing in each localised version.

---

### 4.12 Right to left

- **RTL-1** System UI frameworks support RTL by default and flip system components automatically. **If you use system-provided elements and standard layouts, you may need no changes at all.**
- **RTL-2** Adjust text alignment to match interface direction if the system doesn't. Left-aligned in LTR becomes right-aligned in RTL.
- **RTL-3** **Align a paragraph (three or more lines) based on its own language, not the current context.** Right-aligning an LTR paragraph makes the beginning of each line hard to find. One- and two-line blocks still follow the context's reading direction.
- **RTL-4** Use **consistent alignment for all items in a list**, including items in a different script.
- **RTL-5** **NEVER reverse the order of numerals within a number.** "541", a phone number, a card number - the digits always appear in the same order.
- **RTL-6** **Reverse the order of numerals that show progress or counting direction; never flip the numerals themselves.** Progress bars, sliders, rating controls, and any sequence that communicates order.
- **RTL-7** **Flip controls that show progress from one value to another** - sliders, progress indicators - and reverse the positions of the glyphs marking their start and end values.
- **RTL-8** **Flip controls for navigation or fixed-order access.** A back button must point **right** in RTL; next/previous buttons flip too.
- **RTL-9** **NEVER flip a control that refers to an actual direction or points at an on-screen area.** A control meaning "to the right" always points right.
- **RTL-10** **Increase RTL font size by about 2 pt** to visually balance Arabic or Hebrew against all-caps Latin text in buttons, labels and titles (Arabic and Hebrew have no uppercase).
- **RTL-11** **NEVER flip photographs, illustrations or general artwork.** Flipping often changes meaning, and flipping a copyrighted image could be a violation. If content is strongly connected to reading direction, create a new version instead.
- **RTL-12** **Reverse the positions of images when their order is meaningful** (chronological, alphabetical, favourites).
- **RTL-13** SF Symbols supplies RTL variants and localised symbols for Arabic, Hebrew and others. For custom symbols, specify directionality.
- **RTL-14** **Flip interface icons that represent text or reading direction** - left-aligned bars become right-aligned.
- **RTL-15** Create localised versions of icons that display actual text (signature, rich text, I-beam pointer symbols all have Latin, Hebrew and Arabic versions). If letters communicate something unrelated to reading or writing, design an alternative image without text.
- **RTL-16** **Flip an icon that shows forward or backward motion.** A speaker icon whose sound waves emanate left in LTR must flip so they emanate right in RTL.
- **RTL-17** **NEVER flip logos, or universal signs and marks.** A flipped logo confuses people and can have legal repercussions; people expect the checkmark to look the same everywhere.
- **RTL-18** **In general, don't flip icons depicting real-world objects.** A clock works the same everywhere. Tools slanted for right-handed use don't need flipping - most people are right-handed and flipping is confusing.
- **RTL-19** For a complex custom icon, consider components individually and the overall visual balance. Some components - a badge, slash, magnifying glass - must follow the visual design language regardless of locale (SF Symbols keeps the same backslash for negation in both LTR and RTL). A badge that represents actual UI must flip if that UI flips; a badge that modifies meaning should flip only if flipping preserves both the meaning and the visual balance. Where a component implies handedness, consider preserving the tool's orientation while flipping the base image.

---

### 4.13 Writing (UX copy)

- **WRI-1** **Determine your app's voice** - who you're talking to, what vocabulary is familiar, how you want people to feel. Keep a list of common terms and reference it for consistency.
- **WRI-2** **Match tone to context.** Vary tone by situation - a reached fitness goal versus a failed payment. Situational factors affect both what you say and how you display it.
- **WRI-3** **Be clear.** Check that each word needs to be there. If you can use fewer words, do. **When in doubt, read it out loud.**
- **WRI-4** Write for everyone: simple, plain language; accessibility and localisation in mind; **no jargon, no gendered terminology.**
- **WRI-5** Put the most important information first. Format text to be easy to read. If you're conveying more than one idea, consider breaking it across screens.
- **WRI-6** **Be action-oriented.** Active voice, clear labels. **For buttons and links it's almost always best to use a verb.** "Send" beats "Let's do it!"
- **WRI-7** **NEVER use "Click here."** Use descriptive words - "Learn more about UX writing" - which matters especially for screen-reader users.
- **WRI-8** **Build language patterns.** Consistency builds familiarity and makes future writing easier.
- **WRI-9** **Pick a capitalisation style per UI element type and apply it consistently.** Title case reads formal, sentence case casual - e.g. title case for all alerts, sentence case for all headlines. (Some components, such as button labels, have their own specific guidelines.)
- **WRI-10** In multi-step flows: open with **"Get Started"**, use the button label to hint at the next step or use **"Continue"/"Next"** consistently, and mark completion with **"Done"**.
- **WRI-11** **Use possessive pronouns sparingly.** "Favourites" says the same as "Your Favourites" more succinctly. If you use them, be consistent and don't switch perspective.
- **WRI-12** **Avoid "we" altogether** - it's unclear who "we" is. Not "We're having trouble loading this content" but **"Unable to load content."**
- **WRI-13** **Describe gestures correctly per device.** Never say "click" on iPhone or iPad where you mean "tap".
- **WRI-14** Small screens require brevity. So do large ones - text on a TV must be large enough to read from a distance, and is visible to everyone in the room, so consider who you're addressing.
- **WRI-15** **Provide clear next steps on blank screens.** An empty state is a chance to welcome and educate, but an empty screen is daunting if it isn't obvious what to do - guide people to an action and give them a button or link. **Empty states are temporary, so never put crucial information there** - it will disappear.
- **WRI-16** **Write clear error messages.** Best is to help people avoid the error. When one is necessary: display it **as close to the problem as possible**, **avoid blame**, and **be clear about what to do**. "Choose a password with at least 8 characters" beats "That password is too short".
- **WRI-17** **NEVER use interjections like "oops!" or "uh-oh."** They're unnecessary and sound insincere.
- **WRI-18** If language alone can't address an error likely to affect many people, **that's a signal to rethink the interaction**, not to write better copy.
- **WRI-19** Choose the right delivery method for a message based on urgency, importance, context, whether it needs immediate action, and how much supporting information is needed - notification, alert, or action sheet.
- **WRI-20** **Keep settings labels clear and simple**, and add an explanation where the label isn't enough. **Describe what the setting does when turned on** and let people infer the opposite.
- **WRI-21** **Give a direct link or button to a setting rather than describing where to find it.**
- **WRI-22** **Show hints in text fields.** Label every field clearly and use hint or placeholder text that shows the expected format - "name@example.com" - or describes the information - "Your name".
- **WRI-23** Show field errors **right next to the field**, and instruct rather than scold. **"Use only letters for your name"** beats "Don't use numbers or symbols", and both beat the robotic **"Invalid name."**

---

### 4.14 Branding

- **BRA-1** Use your brand's voice and tone in **all** written communication you display.
- **BRA-2** **Apply the accent colour judiciously.** Using your brand colour too broadly overwhelms the interface and dilutes its impact. **Minimise its use on controls**; use it intentionally for **primary actions or status indicators** - an unread badge, the selected tab's icon.
- **BRA-3** To express brand through colour, **move the colour into the content layer**, where it scrolls beneath Liquid Glass controls and gets picked up dynamically. **[27]**
- **BRA-4** A custom font is fine if it's legible at all sizes and supports Bold Text and Dynamic Type. **A good pattern: custom font for headlines and subheadings, system fonts for body copy and captions**, because the system fonts are designed for optimal legibility at small sizes.
- **BRA-5** **Express your brand with familiar components.** If you customise a component's appearance, keep sizing, placement and behaviour preserving a familiar, platform-appropriate experience.
- **BRA-6** **Branding always defers to content.** Screen space spent on an element that only displays a brand asset is space taken from content people care about.
- **BRA-7** Place UI in expected locations, use standard symbols for common actions, and follow established conventions for navigation and modality. **Even a highly stylised interface can be approachable if its behaviours and patterns stay familiar.**
- **BRA-8** **NEVER display your logo throughout the app** unless it's essential for context. People seldom need reminding which app they're in.
- **BRA-9** **NEVER use a launch screen as a branding opportunity.** It disappears too quickly to convey anything. Use a welcome or onboarding screen instead.
- **BRA-10** **Apple trademarks must not appear in your app name or images.**

---

### 4.15 Privacy

- **PRV-1** **Request access only to data you actually need.** Asking for more than a feature needs - or asking before a person shows interest in the feature - makes the app hard to trust. Make permission requests as specific as possible.
- **PRV-2** Be transparent about how you collect and use data. Respect Hide My Email and Mail Privacy Protection, and understand your app-tracking obligations.
- **PRV-3** **Process data on the device where possible**, avoiding round trips to a remote server.
- **PRV-4** Adopt system privacy protections and security best practices.
- **PRV-5** Things you must request permission for: personal data (location, health, financial, contact, other PII); user-generated content (email, messages, calendar, contacts, gameplay information, Apple Music activity, HomeKit data, audio/video/photo content); protected resources (Bluetooth peripherals, home automation, Wi-Fi connections, local networks); device capabilities (camera, microphone); the advertising identifier.
- **PRV-6** **Request permission only when the app clearly needs access** - ideally at the moment someone uses the feature that requires it.
- **PRV-7** **Avoid requesting permission at launch** unless the data is required for the app to function at all.
- **PRV-8** Write the **purpose string** as a brief, complete sentence: **straightforward, specific, sentence case, active voice, ending in a period.** Apple's own example of good and bad:
  - Good: *"The app records during the night to detect snoring sounds."* - active, clear on how and why.
  - Bad: *"Microphone access is needed for a better experience."* - passive, vague justification.
  - Bad: *"Turn on microphone access."* - imperative, no justification at all.
- **PRV-9** If you show a **pre-alert screen** before the system permission alert: **include exactly one button**, and make it obvious that it opens the system alert. **NEVER title it "Allow"** - use **"Continue"** or **"Next"**. **NEVER include any other action**, including a way to close or cancel out of the screen.
- **PRV-10** For **tracking**, the system alert must be shown before you collect any tracking data. **NEVER precede it with a screen that could confuse or mislead.** Designs that cause **App Store rejection** under guideline 5.1.1(iv): offering incentives; a screen that looks like a permission request; displaying an image of the alert; annotating the screen behind the alert.
- **PRV-11** Consider the **location button** (iOS, iPadOS) for one-time location sharing. You may customise its system-provided title, filled or outlined glyph, background colour, title/glyph colour, and corner radius - and nothing else. **You are responsible for text fitting without truncation at all accessibility sizes and in every localisation.** If the system finds consistent problems with your customised button, **it will stop granting location access when people tap it.**
- **PRV-12** **Avoid relying solely on passwords.** Prefer **passkeys**; if you keep passwords, add two-factor authentication, and use Face ID / Optic ID / Touch ID to protect apps people stay logged into.
- **PRV-13** **Store sensitive information in a keychain. NEVER store passwords or secure content in plain-text files**, even with restricted file permissions.
- **PRV-14** **NEVER invent a custom authentication scheme.** Prefer passkeys, Sign in with Apple, Password AutoFill.
- **PRV-15 (macOS)** Sign the app with a valid **Developer ID** if distributing outside the store. **Sandbox** the app - required for the Mac App Store. **Never assume who is signed in**; fast user switching means several people may be active on the same system.

---

## 5. Component rules

Every rule here is a component-specific requirement from the HIG. Components marked (macOS) don't exist or don't apply on iOS/iPadOS.

### 5.1 Buttons

A button initiates an **instantaneous** action. Three attributes define it: **style** (size, colour, shape), **content** (symbol, text label, or both), **role** (system-defined semantic meaning).

- **BTN-1** Include enough space around a button that people can visually distinguish it from surrounding components and content.
- **BTN-2** **Always include a press state for a custom button.** Without one the button feels unresponsive and people wonder whether it registered their input.
- **BTN-3** Use a **prominent** style for the most likely action in a view - the system then applies the accent colour to the button's background.
- **BTN-4** **Use style, not size, to distinguish the preferred choice.** Buttons of the same size signal a coherent set of choices.
- **BTN-5** **Avoid applying a similar colour to button labels and content-layer backgrounds.** If the content layer is already bright and colourful, prefer the default monochromatic label appearance.
- **BTN-6** Associate familiar actions with familiar icons (`square.and.arrow.up` for share).
- **BTN-7** Use text when a short label communicates more clearly than an icon - a few words that succinctly describe what the button does.
- **BTN-8** The four roles: **normal** (no specific meaning), **primary** (the default - the button people are most likely to choose; it responds to Return), **cancel**, **destructive** (uses system red).
- **BTN-9** **NEVER assign the primary role to a destructive action**, even if it's the most likely choice - people sometimes choose a primary button without reading it first.
- **BTN-10 (iOS, iPadOS)** Configure a button to show an **activity indicator** when its action doesn't complete instantly. It saves space while explaining the delay.
- **BTN-11 (macOS)** **Append a trailing ellipsis** to a push button's title when it opens another window, view or app. Throughout the system an ellipsis signals that people can provide additional input.
- **BTN-12 (macOS)** Use a flexible-height push button only for tall or variable-height content; it keeps the same corner radius and content padding as a regular push button.
- **BTN-13 (macOS)** Consider supporting **spring loading** - on a Magic Trackpad, activating a button by dragging items over it and force-clicking without dropping them.
- **BTN-14 (macOS)** **Square (gradient) buttons** contain symbols or icons, not text; they sit within or beneath the view they affect. **NEVER put them in a toolbar or status bar.** Don't label them.
- **BTN-15 (macOS)** **Help buttons**: circular, consistently sized, containing a question mark. Open the help topic relevant to the current context. **No more than one per window.** Never in the window frame. Never introduce with descriptive text. Placement:

| View style | Help button location |
|---|---|
| Dialog with dismissal buttons (OK, Cancel) | Lower corner opposite the dismissal buttons, vertically aligned with them |
| Dialog without dismissal buttons | Lower-left or lower-right corner |
| Settings window or pane | Lower-left or lower-right corner |

- **BTN-16 (macOS)** **Image buttons**: about **10 px of padding** between the image edges and the button edges (the edges define the clickable area even when invisible). If a label is needed, put it **below** the button.

### 5.2 Toolbars

A toolbar carries the **title of the current view**, **navigation controls** (back, forward, search fields) and **actions** (buttons, menus), arranged horizontally along the top or bottom edge, grouped into logical sections. A toolbar acts on content; a **tab bar** is specifically for navigating between areas.

- **TBR-1** **Choose items deliberately to avoid overcrowding.** People must be able to distinguish and activate each one.
- **TBR-2** The system adds an overflow menu automatically on macOS and iPadOS when items no longer fit. **NEVER add an overflow menu manually**, and **avoid layouts that cause toolbar items to overflow by default.**
- **TBR-3** Add a **More** menu for additional actions; prioritise the less important actions into it.
- **TBR-4 (iPadOS, macOS)** Let people **customise** the toolbar. Especially valuable in apps with many items, advanced functionality not everyone needs, or long sessions.
- **TBR-5** **Reduce the use of toolbar backgrounds and tinted controls** - custom backgrounds can overlay or interfere with the background effects the system provides. **[27]**
- **TBR-6** Avoid applying a similar colour to toolbar item labels and content-layer backgrounds.
- **TBR-7** **Prefer standard components in a toolbar** - standard buttons, text fields, headers and footers have corner radii **concentric with the bar corners** by default.
- **TBR-8** Consider temporarily hiding toolbars for a distraction-free experience.
- **TBR-9** **Provide a useful title for each window.**
- **TBR-10** **NEVER title a window with your app's name** - it tells people nothing about the content hierarchy.
- **TBR-11** **Keep the title under 15 characters** so there's room for other controls.
- **TBR-12** Use the **standard Back and Close buttons.**
- **TBR-13** Provide actions supporting the main tasks; prioritise the commands people are most likely to want. Never make people guess or experiment to learn what an item does.
- **TBR-14** **Prefer system-provided symbols without borders** - familiar, automatically coloured and vibrant, consistent interaction response.
- **TBR-15** **Use the `.prominent` style for key actions such as Done or Submit** - it separates and tints the action, creating a clear focal point. **[27]**
- **TBR-16** Three item positions and what belongs in each:
  - **Leading edge** - return-to-previous-document and show/hide sidebar at the far leading edge, then the view title.
  - **Centre** - common, useful controls; the view title if it isn't on the leading edge.
  - **Trailing edge** - important always-available items, inspector buttons, an optional search field, and the More menu (which also hosts toolbar customisation).
- **TBR-17** Group items logically by function and frequency of use.
- **TBR-18** Put navigation controls and critical actions (Done, Close, Save) in **dedicated, familiar, visually distinct sections.**
- **TBR-19** **Keep groupings and placement consistent across platforms.**
- **TBR-20** **Minimise the number of groups** - too many feels cluttered, even with iPad and Mac's extra space.
- **TBR-21** **Keep actions with text labels separate from actions with symbols.** Adjacent, they create the illusion of one combined action.
- **TBR-22 (iOS)** Prioritise only the most important items for the main toolbar area; space is very limited.
- **TBR-23 (iOS)** Use a **large title** to keep people oriented - it transitions to a standard title on scroll and back to large at the top.
- **TBR-24 (iPadOS)** A toolbar and a tab bar **can coexist in the same horizontal space** at the top of the view.
- **TBR-25 (macOS)** **Make every toolbar item available as a command in the menu bar.** People can customise or hide the toolbar, so it can never be the only place a command exists.

### 5.3 Tab bars

- **TAB-1** **Use a tab bar for navigation, NEVER for actions.**
- **TAB-2** **Keep the tab bar visible as people navigate.** Hiding it makes people forget where they are.
- **TAB-3** Use the appropriate number of tabs - weigh the complexity of more tabs against how often people need each section. **Fewer tabs are generally easier to navigate.**
- **TAB-4** **Avoid overflow tabs.** The number of visible tabs varies with device size and orientation.
- **TAB-5** **NEVER disable or hide tab bar buttons**, even when their content is unavailable - it makes the app look unstable and unpredictable.
- **TAB-6** **Include tab labels.**
- **TAB-7** Prefer SF Symbols for tab icons so they adapt to different contexts.
- **TAB-8** Use a **badge** - a red oval with white text, a number or an exclamation point - to indicate new or updated information warranting attention.
- **TAB-9** Avoid applying a similar colour to tab labels and content-layer backgrounds; prefer monochromatic tab bars over colourful content, or an accent colour with sufficient differentiation.
- **TAB-10 (iOS)** The tab bar **floats above content at the bottom of the screen** on Liquid Glass, letting content peek through. With an attached accessory (like Music's MiniPlayer) you can **minimise the tab bar** and move the accessory inline when a person scrolls down; tapping a tab or scrolling to the top exits the minimised state. A dedicated **search tab** can sit at the trailing end. **[27]**
- **TAB-11 (iPadOS)** The tab bar appears **near the top** of the screen, either fixed or with a button that converts it to a sidebar. **Prefer a tab bar for navigation**, and let people customise which items appear in it.

### 5.4 Sidebars

- **SDB-1** A sidebar needs a lot of vertical **and** horizontal space. When space is limited, a tab bar gives a better navigation experience.
- **SDB-2** **Extend visually rich content beneath the sidebar** - on iOS, iPadOS and macOS sidebars float above content in the Liquid Glass layer. **[27]**
- **SDB-3** Let people **customise** the sidebar's contents and order.
- **SDB-4** Group hierarchy with **disclosure controls** if there's a lot of content, to keep vertical space manageable.
- **SDB-5** Use familiar SF Symbols for sidebar items.
- **SDB-6** Let people **hide** the sidebar.
- **SDB-7** **In general show no more than two levels of hierarchy in a sidebar.** Deeper than two levels: use a split view with a content list between sidebar items and the detail view.
- **SDB-8** If you do use two levels, title each group with a succinct, descriptive label; omit unnecessary words.
- **SDB-9** **Make sure any sidebar icon colours serve a clear purpose.** By default sidebar icons use the app's accent colour. (On macOS a fixed-colour sidebar icon is never overridden by the person's accent-colour choice, because its colour carries meaning.)
- **SDB-10 (iOS, iPadOS)** **Consider a tab bar first** - it gives more room for content and enough flexibility for most apps' main areas.
- **SDB-11 (macOS)** Sidebar row height, text and glyph size depend on its size - small, medium or large. You can set it programmatically, but **people can also change it** in General settings.
- **SDB-12 (macOS)** Consider automatically hiding and revealing the sidebar as the window resizes.
- **SDB-13 (macOS)** **Avoid putting critical information or actions at the bottom of a sidebar** - people relocate windows in ways that hide the bottom edge.

### 5.5 Menus

- **MNU-1** Write a label that clearly and succinctly describes each item. For an item that initiates an action, use a **verb or verb phrase** - View, Close, Select.
- **MNU-2** **Use title-style capitalisation** - capitalise every word except articles, coordinating conjunctions and short prepositions, and always capitalise the last word regardless of part of speech.
- **MNU-3** **Remove articles (a, an, the)** from menu-item labels. They lengthen labels without enhancing understanding.
- **MNU-4** Show when an item is unavailable - dimmed and unresponsive.
- **MNU-5** **Append an ellipsis (…) when the action requires more information before it can complete.**
- **MNU-6** Represent common actions with the system's standard icons.
- **MNU-7** **Use menu item icons sparingly and with purpose.**
- **MNU-8** **Provide icons for all items in a group, or none of them.** Mixed treatment breaks visual consistency and balance.
- **MNU-9** **List important or frequently used items first** - people scan from the top.
- **MNU-10** Group logically related items (Copy/Cut/Paste).
- **MNU-11** **Keep all logically related commands in the same group even when their importance differs.** People expect Paste and Match Style next to Paste, however rarely they use it.
- **MNU-12** Be mindful of menu length; a long menu takes more time and attention and people may miss the command they want.
- **MNU-13** **Use submenus sparingly** - each adds complexity and hides its contents.
- **MNU-14** **Limit submenus to a single level.**
- **MNU-15** **Keep a submenu available even when all its items are unavailable** - people need to be able to open it and learn what it contains.
- **MNU-16** **Prefer a submenu to indenting menu items.** Indentation is inconsistent with the system and doesn't express relationships clearly.
- **MNU-17** For a two-state attribute, prefer **one item with a changeable label** (Show Map ↔ Hide Map) over two separate items.
- **MNU-18** **Include a verb if a changeable label isn't clear enough** - people can't tell whether "HDR On" is an action or a state.
- **MNU-19** Display both items instead of one toggled item when it helps people see both actions or states at once.
- **MNU-20** Use a **checkmark** to show an attribute is in effect - easy to scan for.
- **MNU-21** Offer an item that removes multiple toggled attributes at once (a **Plain** item that clears all formatting).
- **MNU-22 (iOS, iPadOS)** Three menu layouts: **Small** (a row of four items above a list), **Medium** (a row of three items above a list), **Large** (the default - everything in a list). Choose small or medium when it streamlines choices.

### 5.6 Context menus

Revealed by: touch-and-hold or pinch-and-hold (iOS, iPadOS, visionOS); Control-click (macOS, iPadOS); secondary click on a Magic Trackpad (macOS, iPadOS).

- **CTX-1** **Prioritise relevancy.** A context menu isn't for advanced or rarely used items - it's for the commands people are most likely to need right now.
- **CTX-2** **Aim for a small number of items.** Too long is hard to scan and scroll.
- **CTX-3** **Support context menus consistently throughout the app.** Providing them in some places and not others makes people think something is broken.
- **CTX-4** **Always make context menu items available in the main interface too.**
- **CTX-5** Keep submenus to one level.
- **CTX-6** **Hide unavailable items - don't dim them.** Unlike a regular menu, a context menu shows only what's relevant to the current selection.
- **CTX-7** Place the most frequently used items where people encounter them first - reading starts nearest where their finger or pointer opened the menu.
- **CTX-8** **NEVER show keyboard shortcuts in a context menu.** It's already a shortcut; showing them is redundant. Show them in the app's main menus.
- **CTX-9** Use separators to group items.
- **CTX-10 (iOS, iPadOS)** **List destructive items (Delete, Remove) at the end of the menu and mark them destructive.**
- **CTX-11** A context menu **seldom displays a title.** Include one only when it clarifies the menu's effect - e.g. stating the number of selected messages so people remember the command affects all of them.
- **CTX-12** Represent item actions with familiar icons.
- **CTX-13 (iOS, iPadOS)** **Provide either a context menu or an edit menu for an item, never both** - it confuses people and makes intent hard for the system to detect.
- **CTX-14 (iOS, iPadOS)** Prefer a **graphical preview** that clarifies the target of the menu's commands - a condensed version of the actual content - and make sure it looks good as it animates out of the content.

### 5.7 Alerts

- **ALR-1** **Use alerts sparingly** - they interrupt the current task.
- **ALR-2** **NEVER use an alert merely to provide information.** People don't appreciate an interruption that's informative but not actionable.
- **ALR-3** **NEVER alert for common, undoable actions, even destructive ones.** Deleting an email or a file is already intentional and undoable.
- **ALR-4** **NEVER show an alert when your app starts.** Design a discoverable way to surface important new information instead.
- **ALR-5** An alert displays a title, optional informative text, and **up to three buttons**. iOS/iPadOS/macOS alerts can include a text field. macOS alerts can add an icon, an accessory view, a suppression checkbox and a Help button.
- **ALR-6** **Be direct, with a neutral, approachable tone.** Never oblique, never accusatory, and never mask the severity of the issue.
- **ALR-7** Write a title that describes the situation clearly and succinctly - complete and specific without being verbose.
- **ALR-8** Include informative text only if it adds value; keep it short, in complete sentences, **sentence-style capitalisation**, proper punctuation.
- **ALR-9** **NEVER explain what the alert's buttons do.** If the text and titles are clear, no explanation is needed.
- **ALR-10** Include a text field only if you need input to resolve the situation.
- **ALR-11** **One or two words per button title**, describing the *result* of choosing it.
- **ALR-12** **Avoid "OK" as the default button title unless the alert is purely informational.** Its meaning is unclear when you're asking people to confirm something.
- **ALR-13** Place the most likely button **on the trailing side in a row**, or **at the top in a stack.**
- **ALR-14** Use the **destructive style** for a destructive action people **didn't deliberately choose**. When they did choose it deliberately (Empty Trash), don't style it destructively - the button performs their original intent.
- **ALR-15** **If there's a destructive action, include a Cancel button. Always title it exactly "Cancel."**
- **ALR-16** Provide alternative ways to cancel: exit to the Home Screen (iOS, iPadOS); **Esc or Command-period** on an attached keyboard (iOS, iPadOS, macOS).
- **ALR-17 (iOS, iPadOS)** **Use an action sheet, not an alert, for choices related to an intentional action.**
- **ALR-18 (iOS, iPadOS)** **Avoid alerts that scroll.** Keep titles short and add a message only when necessary.
- **ALR-19 (macOS)** **Use a caution symbol sparingly.** Overusing `exclamationmark.triangle` diminishes its significance.

### 5.8 Action sheets (iOS, iPadOS)

- **ASH-1** Use an action sheet, not an alert, for choices related to an action **the person initiated**.
- **ASH-2** Use action sheets sparingly - they interrupt.
- **ASH-3** **Keep titles short enough for a single line.**
- **ASH-4** Provide a message only if necessary - title plus context is usually enough.
- **ASH-5** Provide a **Cancel button at the bottom** when an action might destroy data.
- **ASH-6** **Put destructive buttons at the top**, in the destructive style, where they're most noticeable.
- **ASH-7** **Use an action sheet, not a menu, for choices related to an action** - people are accustomed to it.
- **ASH-8** **Avoid letting an action sheet scroll.** More buttons means more time and effort to choose.

### 5.9 Sheets

- **SHT-1** A sheet is for a **scoped task closely related to the current context.** On macOS it is always **modal**; on iOS and iPadOS it can be modal or **nonmodal**.
- **SHT-2** Three navigation buttons and their meanings: **Cancel/Close** dismisses without saving; **Done** dismisses after completing or explicitly saving; **Back** moves to a previous step - **Back is not a dismissal.**
- **SHT-3** For complex or prolonged flows consider alternatives - iOS/iPadOS full-screen modal style works better for video, photos, camera views, or multi-step editing.
- **SHT-4** **Display only one sheet at a time from the main interface.**
- **SHT-5** Use a nonmodal presentation for supplementary items that affect the parent task - a split view, a macOS panel, or an iOS/iPadOS nonmodal sheet.
- **SHT-6** **Always pair a Done button with either Cancel or Back.** **NEVER show Cancel, Done and Back together.**
- **SHT-7 (iOS, iPadOS)** For a single-view sheet: **Cancel on the leading edge of the top toolbar, Done on the trailing edge.**
- **SHT-8 (iOS, iPadOS)** Resizable sheets rest at **detents.** Sheets automatically support the **large** detent; adding **medium** lets them rest at both; specifying only medium prevents full height.
- **SHT-9 (iPhone)** Consider supporting the **medium detent** for progressive disclosure - the share sheet shows the most relevant items there without resizing.
- **SHT-10** **Include a grabber in a resizable sheet** - it shows the sheet can be dragged, and tapping it cycles through detents.
- **SHT-11** **Support swiping to dismiss.** People expect a vertical swipe rather than a button tap.
- **SHT-12 (iPadOS)** **Prefer the page or form sheet presentation styles** - default size, content centred on a dimmed background, consistent experience.
- **SHT-13 (macOS)** Present a sheet at a **reasonable default size**; people don't generally expect to resize sheets.
- **SHT-14 (macOS)** **Let people interact with other app windows without dismissing the sheet.** Bring the parent window (and its modeless document panels) forward when the sheet opens.
- **SHT-15 (macOS)** **Use a panel instead of a sheet when people need to repeatedly provide input and observe results** - find and replace, for example.

### 5.10 Popovers

- **POP-1** Use a popover for **a small amount** of information or functionality - a few related tasks, because it disappears after interaction.
- **POP-2** **Make the popover's arrow point as directly as possible at the element that revealed it.**
- **POP-3** **Use a Close button only for confirmation and guidance** - where it clarifies exiting with or without saving.
- **POP-4** **Always save work when automatically closing a nonmodal popover.** People dismiss them unintentionally by clicking outside.
- **POP-5** **Show one popover at a time.**
- **POP-6** **NEVER show another view over a popover**, except an alert.
- **POP-7** Where possible, let people close one popover and open another with a single click or tap.
- **POP-8** **Avoid making a popover too big** - only big enough for its contents and to point at its source.
- **POP-9** Provide a smooth transition when changing a popover's size.
- **POP-10** **NEVER use the word "popover" in help documentation.** Refer to the task or selection instead.
- **POP-11** **NEVER use a popover to show a warning.** People can miss it or close it accidentally.
- **POP-12 (iOS, iPadOS)** **Avoid popovers in compact views.** Adjust the layout by size class instead.
- **POP-13 (macOS)** Consider letting people **detach** a popover into a panel, and **keep the detached panel looking similar** so people maintain context.

### 5.11 Scroll views and scroll edge effects

- **SCR-1** **Support default scrolling gestures and keyboard shortcuts.**
- **SCR-2** **Make it apparent when content is scrollable** - scroll indicators aren't always visible.
- **SCR-3** **NEVER nest a scroll view inside another scroll view with the same orientation.**
- **SCR-4** Consider page-by-page scrolling where fixed-amount scrolling suits the content, and show a **page control** when you do.
- **SCR-5** Scroll automatically only when it helps people find their place, and **only as much as necessary to preserve context**:
  - when an operation selects content or places the insertion point in a hidden area (bring a search result into view);
  - when people start entering information somewhere not currently visible;
  - when the pointer moves past the edge of the view during a selection - follow it;
  - when people select something, scroll away, then act on the selection - scroll the selection back into view first.
- **SCR-6** If you support zoom, set sensible maximum and minimum scale values.
- **SCR-7** A **scroll edge effect** visually separates floating interface elements (toolbars) from the scrolling content behind them. **[27]**
- **SCR-8** **Prefer the automatic scroll edge effect style** over hard or soft.
- **SCR-9** **Only use a scroll edge effect when a scroll view is behind floating interface elements. Scroll edge effects aren't decorative.**
- **SCR-10** **Apply one scroll edge effect per view.** In iPad and Mac split views each pane can have its own - **keep them the same height so they stay aligned.**

### 5.12 Windows (iPadOS, macOS)

- **WIN-1** Two conceptual types: a **primary** window (main navigation and content) and an **auxiliary** window (one specific task or area, no navigation to other app areas, usually with a close button).
- **WIN-2** **Windows must adapt fluidly to different sizes** to support multitasking and multi-window workflows.
- **WIN-3** Choose the right moment to open a new window - it's good for multitasking and preserving context.
- **WIN-4** Offer "view in a new window" as an option; **avoid opening new windows as default behaviour** unless it clearly benefits the experience.
- **WIN-5** **NEVER create custom window UI.**
- **WIN-6** **Use the word "window" in user-facing content**, whatever the window's type.
- **WIN-7 (iPadOS)** Windows are either **full screen** (switched via the app switcher) or **windowed** (freely resizable), depending on the person's Multitasking & Gestures setting. **[27]**
- **WIN-8 (iPadOS)** **Make sure window controls don't overlap toolbar items** - when windowed, controls sit at the leading edge of the toolbar.
- **WIN-9 (iPadOS)** Consider a gesture to open content in a new window (pinch to expand a Notes item).
- **WIN-10 (macOS)** A window is a **frame** (window controls, toolbar, rarely a bottom bar) plus a **body**.
- **WIN-11 (macOS)** Three states: **main** (frontmost), **key** (active - accepts input), **inactive**. The key window uses colour in the close/minimise/zoom controls; inactive windows and non-key main windows use grey. **Custom windows must use the system-defined appearances** - people rely on those differences to know which window takes their input.
- **WIN-12 (macOS)** **Avoid putting critical information or actions in a bottom bar**, because people relocate windows in ways that hide the bottom edge. If you must have one, use it only for a small amount of information directly related to the window's contents or a selected item.

### 5.13 Text fields

- **TXF-1** Use a text field for **a small amount** of information - a name, an email address. For larger amounts use a text view.
- **TXF-2** **Show a hint** (placeholder text) to communicate the field's purpose.
- **TXF-3** **Always use a secure text field for sensitive data** such as a password.
- **TXF-4** **Match the field's size to the quantity of anticipated text** - size helps people gauge how much to provide.
- **TXF-5** **Evenly space multiple text fields**, with enough room that it's obvious which label belongs to which field.
- **TXF-6** **Ensure tabbing between fields moves focus in a logical sequence.**
- **TXF-7** Validate fields when it makes sense, and alert people when input doesn't fit.
- **TXF-8** Use a **number formatter** for numeric data so the field accepts only numbers.
- **TXF-9** Adjust line breaks to the field's needs - by default the system clips text extending beyond the bounds.
- **TXF-10** Consider an **expansion tooltip** to show the full version of clipped or truncated text on hover.
- **TXF-11 (iOS, iPadOS)** **Show the appropriate keyboard type** for the expected input.
- **TXF-12 (iOS, iPadOS)** **Display a Clear button** at the trailing end so people don't have to hold Delete.
- **TXF-13 (iOS, iPadOS)** You can put custom images at either end, or a system-provided button such as Bookmarks.
- **TXF-14 (macOS)** Consider a **combo box** when text input needs to be paired with a list of choices.

### 5.14 Toggles, checkboxes, radio buttons

- **TGL-1** Use a toggle for **two opposing values that affect state**. For choosing from a list, use a pop-up button instead.
- **TGL-2** **Clearly identify what the toggle affects** - usually the surrounding context does this.
- **TGL-3** **Make the visual difference between states obvious** - add or remove a colour fill, show or hide the background shape, change an inner detail such as a checkmark or dot.
- **TGL-4 (iOS, iPadOS)** **Use the switch style only in a list row.** No label is needed there - the row content is the context.
- **TGL-5 (iOS, iPadOS)** **Change a switch's default colour only if necessary.** The default green works in most cases; your accent colour is the alternative.
- **TGL-6 (iOS, iPadOS)** **Outside a list, use a button that behaves like a toggle, not a switch.** Don't add a label explaining its purpose - the icon plus the alternate background appearances should communicate it.
- **TGL-7 (macOS)** **Use switches, checkboxes and radio buttons in the window body, NEVER in a toolbar or status bar.**
- **TGL-8 (macOS)** **Prefer a switch for settings you want to emphasise** - it carries more visual weight than a checkbox, so it suits controlling more functionality.
- **TGL-9 (macOS)** In a grouped form, a **mini switch** matches the height of buttons and other controls, keeping row heights consistent.
- **TGL-10 (macOS)** **In general, don't replace an existing checkbox with a switch.**
- **TGL-11 (macOS)** **Use a checkbox rather than a switch when presenting a hierarchy of settings** - checkboxes align well and communicate grouping.
- **TGL-12 (macOS)** A checkbox has three possible states - **on, off, mixed** (a dash). Reflect the state accurately.
- **TGL-13 (macOS)** Introduce a group of checkboxes with a label when the relationship isn't obvious, and **align the label's baseline with the first checkbox.**
- **TGL-14 (macOS)** **Use radio buttons for more than two mutually exclusive options**, typically in groups of **two to five**. For multiple selection within a set, use checkboxes.
- **TGL-15 (macOS)** **Avoid long lists of radio buttons** - they take space and overwhelm.
- **TGL-16 (macOS)** **For a single on/off setting, prefer a checkbox over a single radio button** - the presence or absence of a checkmark reads more clearly.
- **TGL-17 (macOS)** When displaying radio buttons horizontally, **measure the longest label and use that spacing consistently.**

### 5.15 Sliders

- **SLD-1** Customise track colour, thumb image and tint, and the left/right icons only when it adds value.
- **SLD-2** **Use familiar directions: minimum on the leading side, maximum on the trailing side; minimum at the bottom, maximum at the top for vertical sliders.**
- **SLD-3** Consider supplementing a slider with a text field and stepper, especially over a wide value range, so people can read and enter an exact value.
- **SLD-4 (iOS, iPadOS)** **NEVER use a slider to adjust audio volume.** Use a volume view, which includes a volume slider and an output-device control.
- **SLD-5 (macOS)** Consider **live feedback** as the value changes.
- **SLD-6 (macOS)** Introduce a slider with a label using **sentence-style capitalisation ending in a colon.**
- **SLD-7 (macOS)** Use **tick marks** to increase clarity and accuracy, and consider labelling them.

### 5.16 Steppers

- **STP-1** **Make the value a stepper affects obvious** - the stepper itself displays no value.
- **STP-2** Pair a stepper with a text field when large value changes are likely; steppers suit small changes of a few taps or clicks.
- **STP-3 (macOS)** For large ranges, consider supporting **Shift-click** to change by a larger increment (10× the default, for example).

### 5.17 Pickers

- **PCK-1** Use a picker for **medium-to-long** lists. For a short list of choices, use a **pull-down button** instead.
- **PCK-2** **Use predictable, logically ordered values** - many of a picker's values are hidden before interaction.
- **PCK-3** **NEVER switch views to show a picker.** Display it in context, below or near the field being edited.
- **PCK-4** Consider **less granularity for minutes** in a date picker - the default minute list has 60 values.
- **PCK-5 (iOS, iPadOS)** Date picker styles: **compact** (a button opening a modal), **inline** (wheels for time; an inline calendar for dates), **wheels**, **automatic**. Modes: **date**, **time**, **date and time**, **countdown timer** (up to 23 h 59 m; not available inline or compact). Values and their order depend on device location.
- **PCK-6 (iOS, iPadOS)** **Use the compact style when space is constrained** - it shows the current value in the app's accent colour.
- **PCK-7 (macOS)** Two styles: **textual** and **graphical**.

### 5.18 Segmented controls

- **SEG-1** Use a segmented control for **closely related choices that affect an object, state or view.**
- **SEG-2** Use one when it's important to group functions together or to show selection state clearly - segmented controls **preserve their grouping regardless of view size or location.**
- **SEG-3** **Keep control types consistent within one segmented control.** Never mix action segments into a control that otherwise represents selection state, or show selection state in a control that performs actions.
- **SEG-4** **Limit the number of segments.**
- **SEG-5** **In general keep segment size consistent** - equal widths feel balanced.
- **SEG-6** **Prefer either text or images, not a mix**, within a single segmented control.
- **SEG-7** Use content of **similar size** in each segment, since segments are usually equal width.
- **SEG-8** Use **nouns or noun phrases with title-style capitalisation** for segment labels.
- **SEG-9 (macOS)** **Use a tab view, not a segmented control, for view switching in the main window area.**
- **SEG-10 (macOS)** Consider introductory text to clarify purpose, and labels below symbol segments.
- **SEG-11 (macOS)** Consider supporting spring loading.

### 5.19 Search fields

- **SRF-1** **Use placeholder text** to reinforce the search scope or educate people about what's searchable.
- **SRF-2** **If possible, start searching immediately as a person types** - it feels more responsive and continuously refines results.
- **SRF-3** Consider showing **suggested search terms** - recent searches before search begins, predictive suggestions as people type.
- **SRF-4** **Provide the most relevant results first** to minimise scrolling.
- **SRF-5** Let people filter results, e.g. with a **scope bar** in the results area.
- **SRF-6** A **scope bar** filters among clearly defined categories. **Default to a broader scope and let people refine it** - the broader scope provides context for the full result set.
- **SRF-7** A **token** is a selectable, editable visual representation of a search term that filters additional terms. **Pair tokens with search suggestions**, because people may not know which tokens exist.
- **SRF-8 (iOS)** Three placements for search: **a tab in the tab bar**, **a toolbar at the bottom or top**, or **inline with content.** **[27]**
  - **Standard search tab** - displays uniformly with the rest of the tab bar; creates a dedicated landing page for search. Choose it to provide suggestions, promote discovery and encourage exploration.
  - **Button-appearance search tab** - displays as a separate button; tapping brings up the keyboard with the search field above it immediately. Choose it to help people find what they need fast.
  - **Bottom toolbar** - as an expanded field or a toolbar button depending on space; animates into a search field above the keyboard. **Place search at the bottom if there's room.**
  - **Top toolbar (navigation bar)** - appears as a button, animating into a field above the keyboard or at the top if there's no bottom space. **Use the top when it's important to defer to content at the bottom, or there's no bottom toolbar.**
  - **Inline** - when position alongside the content strengthens the relationship, e.g. filtering within a single view. At the top, **position it above the list it searches and consider pinning it to the top toolbar on scroll.**
- **SRF-9 (iPadOS, macOS)** Keep the search experience as consistent as possible across iPad and Mac.
- **SRF-10 (iPadOS, macOS)** **Put a search field at the trailing side of the toolbar** for most common uses - particularly split-view apps searching across multiple columns (Mail, Notes, Voice Memos).
- **SRF-11 (iPadOS, macOS)** Put search **at the top of the sidebar** when it filters content or navigation there (as Settings does).
- **SRF-12 (iPadOS, macOS)** Put search **as an item in the sidebar or tab bar** when you want an area dedicated to discovery - rich suggestions, categories, content needing space.
- **SRF-13 (iPadOS, macOS)** In a dedicated search area, consider **focusing the field immediately** on navigation - **except on iPad with only a virtual keyboard**, where leaving it unfocused prevents the keyboard unexpectedly covering the view.
- **SRF-14** **Account for window resizing** in the search field's placement; on iPad it resizes fluidly with the window as on Mac.

### 5.20 Virtual keyboards (iOS, iPadOS)

- **VKB-1** **Choose a keyboard type that matches the content.** Available types include ASCII capable, ASCII capable number pad, decimal pad, default, email address, name/phone pad, number pad, numbers and punctuation, phone pad, URL, web search.
- **VKB-2** A virtual keyboard **doesn't support keyboard shortcuts.**
- **VKB-3** Customise the **Return key type** where it clarifies the text-entry experience.
- **VKB-4** A **custom input view** replaces the keyboard inside your app (Numbers uses one for spreadsheet values). Make sure people understand its benefit, and **play the standard keyboard sound while people type** - they expect it.
- **VKB-5** A **custom keyboard** is an app extension usable system-wide (except in secure text fields and phone number fields). Use one only to expose genuinely new input systemwide; for in-app use, build a custom input view instead.
- **VKB-6** **Provide an obvious, easy way to switch between keyboards** - people expect the Globe key behaviour.
- **VKB-7** **Avoid duplicating system keyboard features** - the Emoji/Globe and Dictation keys appear automatically beneath custom keyboards on some devices.
- **VKB-8** Consider providing a keyboard tutorial in your app.
- **VKB-9** **Use the keyboard layout guide** so the keyboard feels integrated and important parts of the interface stay visible.
- **VKB-10** Place custom controls above the keyboard thoughtfully, in an input accessory view.

### 5.21 Lists and tables

- **LST-1** **Prefer displaying text in a list or table** - the row format makes text easy to scan and read.
- **LST-2** Let people edit a table where it makes sense. **People appreciate being able to reorder a list even when they can't add or remove items.**
- **LST-3** Provide appropriate feedback on selection, varying with whether selecting reveals a new view or toggles state.
- **LST-4** **Keep item text succinct** to minimise truncation and wrapping.
- **LST-5** Preserve readability of text that might otherwise be clipped, especially when the table's width can vary.
- **LST-6** **Use descriptive column headings** in a multicolumn table: nouns or short noun phrases, **title-style capitalisation, no ending punctuation.**
- **LST-7** Choose a table or list style that coordinates with the data and the platform, and a row style that fits the information.
- **LST-8 (iOS, iPadOS)** **Use an info button (detail disclosure button in a row) only to reveal more information about the row's content** - it doesn't support navigation through a hierarchy.
- **LST-9 (iOS, iPadOS)** **Avoid adding an index to a table whose rows have trailing controls** such as disclosure indicators.
- **LST-10 (macOS)** Let people **click a column heading to sort** where it provides value, and **let people resize columns.**
- **LST-11 (macOS)** Consider **alternating row colours** in a multicolumn table so people can track values across columns.
- **LST-12 (macOS)** **Use an outline view rather than a table view for hierarchical data.**

### 5.22 Collections

- **COL2-1** **Use the standard row or grid layout whenever possible** - horizontal row or grid is what people expect.
- **COL2-2** Collections are **ideal for image-based content**. **Consider a table instead of a collection for text** - a scrollable list is simpler and more efficient to read.
- **COL2-3** **Make it easy to choose an item.** If getting to an item is too difficult people lose interest before they reach it.
- **COL2-4** Default interactions are tap to select, touch and hold to edit, swipe to scroll. Add custom interactions only when necessary.
- **COL2-5** Consider animation as feedback when people insert, delete or reorder items.
- **COL2-6 (iOS, iPadOS)** **Use caution when making dynamic layout changes.**

### 5.23 Labels

- **LBL-1** Use a label for a small amount of text people don't need to edit. To let people edit a small amount of text, use a text field.
- **LBL-2** **Prefer system fonts** - a label supports Dynamic Type by default.
- **LBL-3** Use the four system label colours to communicate relative importance:

| System colour | Example usage |
|---|---|
| Label | Primary information |
| Secondary label | A subheading or supplemental text |
| Tertiary label | Text describing an unavailable item or behaviour |
| Quaternary label | Watermark text |

- **LBL-4** **Make useful label text selectable** - an error message, a location, an IP address - so people can copy it.

### 5.24 Disclosure controls

- **DSC-1** Use a disclosure control to hide details until they're relevant. **Put the controls people are most likely to use at the top of the disclosure hierarchy, always visible, with advanced functionality hidden by default.**
- **DSC-2** A **disclosure triangle** points **inward from the leading edge** when content is hidden and **down** when visible.
- **DSC-3** **Provide a descriptive label** that indicates what is disclosed or hidden - "Advanced Options".
- **DSC-4** A **disclosure button** points **down** when content is hidden and **up** when visible.
- **DSC-5** **Place a disclosure button near the content it shows and hides.**
- **DSC-6** **Use no more than one disclosure button in a single view.**

### 5.25 Split views

- **SPV-1** **Persistently highlight the current selection in each pane that leads to the detail view** - it clarifies the relationship between panes and keeps people oriented.
- **SPV-2** Consider letting people **drag and drop content between panes.**
- **SPV-3 (iOS)** **Prefer a split view in a regular, not compact, environment** - it needs horizontal space.
- **SPV-4 (iPadOS)** Two or three vertical panes. **Account for narrow, compact and intermediate window widths**, because iPad windows resize fluidly.
- **SPV-5 (macOS)** Panes can be arranged vertically, horizontally or both, with draggable dividers.
- **SPV-6 (macOS)** **Set reasonable default minimum and maximum pane sizes** that keep the divider visible.
- **SPV-7 (macOS)** Let people hide a pane where it makes sense, and **provide multiple ways to reveal a hidden pane** - a toolbar button and a menu command with a keyboard shortcut.
- **SPV-8 (macOS)** **Prefer the thin divider style** - **one point wide**, maximising content space while staying usable.

### 5.26 Progress indicators

- **PRG-1** Two types: **determinate** (well-defined duration - a file conversion) and **indeterminate**, also called an **activity indicator** (unquantifiable - loading, syncing complex data). All progress indicators are **transient**: they appear only while an operation runs and disappear when it completes.
- **PRG-2** **When possible, use a determinate indicator.**
- **PRG-3** **Be as accurate as possible when reporting advancement**, and consider evening out the pace so people feel confident about the remaining time.
- **PRG-4** **Keep progress indicators moving.** A stationary indicator reads as a stalled process or a frozen app.
- **PRG-5** **Switch from indeterminate to determinate** when you learn the duration.
- **PRG-6** **NEVER switch from the circular style to the bar style** - different shapes and sizes, so the transition disrupts the interface and confuses people.
- **PRG-7** Display a description providing additional context if it's helpful - accurate and succinct.
- **PRG-8** **Display a progress indicator in a consistent location.**
- **PRG-9** **When feasible, let people halt processing** with a Cancel button.
- **PRG-10** **Let people know when halting has a negative consequence** - when cancelling loses progress, show an alert offering to confirm or resume.
- **PRG-11 (iOS, iPadOS)** A **refresh control** lets people reload immediately by dragging down. **Still perform automatic content updates periodically** - people expect both. Supply a short title only if it adds value.
- **PRG-12 (macOS)** **Prefer a spinner for background operations or where space is constrained**, and **avoid labelling a spinning indicator** - it appears right after people initiate the process, so a label is usually unnecessary.

### 5.27 Charts

- **CHT-1** A **mark** is the visual representation of a data value; a **scale** maps data values to visual characteristics (position, colour, height).
- **CHT-2** Choose a mark type by what you want to communicate: **bar** for comparing values across categories or showing parts of a whole; **line** for change over time; **point** for individual values as visually distinct marks. **Combine types when it adds clarity** (point marks on a line to highlight individual data points).
- **CHT-3** Use a **fixed** axis range when the bounds never change, a **dynamic** range when possible values vary widely and you want marks to fill the plot area.
- **CHT-4** **Define the lower bound based on mark type and use.** Bar charts usually want **zero** as the lower bound so relative heights are meaningful.
- **CHT-5** **Prefer familiar sequences** in tick and grid-line labels (0, 5, 10 …).
- **CHT-6** Tailor grid lines and labels: **too many grid lines is visually overwhelming and distracts from the data; too few makes values hard to estimate.**
- **CHT-7** **Write descriptions that help people understand what the chart does before they view it.**
- **CHT-8** **Summarise the main message of the chart.** Displaying supporting data isn't enough - people need to grasp the key information quickly.
- **CHT-9** **Establish a consistent visual hierarchy where the data is most prominent** and descriptions and axes provide context without competing.
- **CHT-10** **In a compact environment, maximise the width of the plot area**, and keep vertical-axis labels as short as possible without losing clarity.
- **CHT-11** **Make every chart accessible.** Charts, like all infographics, must be fully accessible regardless of how people perceive content.
- **CHT-12** Let people interact with the data where it makes sense, but **NEVER require interaction to reveal critical information.**
- **CHT-13** **Make it easy for everyone to interact** - marks too small to target with a finger or pointer are hard for people with reduced motor control and uncomfortable for everyone.
- **CHT-14** Make an interactive chart navigable by **keyboard (including Full Keyboard Access) and Switch Control**, which visit elements in a linear sequence.
- **CHT-15** **Help people notice important changes** - if marks or axes change unnoticed, people misread the chart.
- **CHT-16** **Align the chart with surrounding interface elements** - usually leading edge to leading edge.
- **CHT-17** **NEVER rely solely on colour** to differentiate data or communicate essential information in a chart.
- **CHT-18** **Add visual separation between contiguous areas of colour**, e.g. between stacked marks in a bar.
- **CHT-19** Consider **Audio Graphs** for VoiceOver users, customised with a chart title and descriptive summary.
- **CHT-20** A chart often needs **an accessibility label per important or interactive element**, not one label for the whole thing. Decide by purpose, scope and mark density whether to describe each mark or groups of marks.
- **CHT-21** Writing chart accessibility labels:
  - **Prioritise clarity and comprehensiveness** - a bare data value is rarely enough without the date or location that contextualises it.
  - **NEVER use subjective terms** - "rapidly", "gradually", "almost" communicate your interpretation, not the data.
  - **Avoid ambiguous formats and abbreviations** - "June 6" beats "6/6"; "60 minutes" or "60 meters" beats "60m".
  - **Describe what the details represent, not what they look like.**
  - **Be consistent about which axis you mention first.**
- **CHT-22** **Hide visible axis and tick labels from assistive technologies** - they're for visual assessment and duplicate what your accessibility labels say.

### 5.28 Boxes

- **BOX-1** **Keep a box relatively small compared with its containing view.** As it approaches the size of the window, it stops communicating separation and starts crowding other content.
- **BOX-2** **Use padding and alignment rather than nested boxes** to communicate subgrouping - nested borders make an interface feel busy and constrained.
- **BOX-3** Provide a succinct introductory title only if it clarifies the contents, written as a brief phrase with **sentence-style capitalisation.**
- **BOX-4 (iOS, iPadOS)** Boxes use the **secondary and tertiary background colours** by default.
- **BOX-5 (macOS)** macOS displays a box's title **above** it by default.

### 5.29 The menu bar (macOS, and iPadOS)

Menu order, always: **YourAppName, File, Edit, Format, View, app-specific menus, Window, Help.** macOS adds the Apple menu on the leading side and menu bar extras on the trailing side. On iPad, menu bar menus appear in the same order with the same familiar item sets, and **iPadOS keyboard shortcuts use the same patterns as macOS.**

- **MBR-1** **Support the default system-defined menus and their ordering.**
- **MBR-2** **Always show the same set of menu items**, even when unavailable in the current context - visibility is how people learn what the app can do.
- **MBR-3** Represent menu item actions with familiar icons.
- **MBR-4** **Support the standard keyboard shortcuts** for every standard menu item you include (Copy, Cut, Paste, Save, Print).
- **MBR-5** **Prefer short, one-word menu titles** - display size and menu bar extras affect spacing.

**App menu**
- **MBR-6** **About YourAppName** comes first, followed by a separator so it sits alone in its group. Use a **short name of 16 characters or fewer** and **don't include a version number** in it.
- **MBR-7** **Settings…** is for **app-level settings only.** Document-specific settings go in the File menu. On iPadOS, reserve Settings for opening your app's page in iPadOS Settings; if you have an internal preferences area, link to it with a separate item beneath Settings in the same group.
- **MBR-8** List custom app-configuration items **after** Settings, in the same group.
- **MBR-9** macOS-only items in this menu: Services, Hide YourAppName, Hide Others, Show All. **Quit YourAppName** (Option turns it into Quit and Keep Windows). Use the same short app name throughout.

**File menu** - standard items and their rules:
- **New Item** - name the type of item the app creates (Calendar uses Event and Calendar).
- **Open** - add an ellipsis when people must select an item in a separate interface.
- **Open Recent** - list recognisable document and filenames, **not file paths**, **most recently opened first**, typically with a **Clear Menu** item.
- **Close** (Option → Close All; in a tab-based window **Close Tab** replaces Close - consider adding a **Close Window** item so people can close the whole window in one action). **Close Tab** (Option → Close Other Tabs). **Close File** closes the file and all its associated windows - support it if your app can open multiple views of one file.
- **Save** - **automatically save changes periodically** so people don't have to keep choosing Save; prompt for name and location for a new document; for multiple formats, **prefer a pop-up menu in the Save sheet** over separate commands. **Save All** saves all open documents.
- **Duplicate** (Option → Save As) - **prefer Duplicate over Save As, Export, Copy To and Save To**, because those don't clarify the relationship between the original and the new file.
- **Rename…**, **Move To…**
- **Export As…** - **reserve it for exporting into a format your app doesn't normally handle.** The current document stays open; the exported file doesn't open.
- **Revert To** - with autosaving on, lists recent versions plus the version browser.
- **Page Setup…** - only for printing parameters that apply to a specific document. Global parameters (printer name) or frequently changed ones (number of copies) belong in the **Print…** panel.

**Edit menu**
- **MBR-10** **Decide whether Find items belong in Edit or File.** If the app searches for files or objects rather than text, Find may belong in the File menu.
- **MBR-11** **Clarify the target of Undo and Redo** by appending the operation - "Undo Paste and Match Style", "Undo Typing".
- **MBR-12** **Provide a Delete item, not Erase or Clear.** Delete is the equivalent of pressing the Delete key, so naming must be consistent. Delete removes without placing on the Clipboard; Cut copies to the Clipboard first. **Differentiate the two when both exist.**
- **MBR-13** Standard submenus: **Find** (Find, Find and Replace, Find Next, Find Previous, Use Selection for Find, Jump to Selection); **Spelling and Grammar**; **Substitutions** (Smart Copy/Paste, Smart Quotes, Smart Dashes, Smart Links, Data Detectors, Text Replacement); **Transformations** (Make Uppercase, Make Lowercase, Capitalize); **Speech**. The system automatically adds **Start Dictation** and **Emoji & Symbols** at the bottom.

**Format menu** - **Font** submenu (Show Fonts, Bold, Italic, Underline, Bigger, Smaller, Show Colors, Copy Style, Paste Style) and **Text** submenu (Align Left, Align Center, Justify, Align Right, Writing Direction, Show Ruler, Copy Ruler, Paste Ruler).

**View menu**
- **MBR-14** **Provide a View menu even if you support only a subset of the standard view functions** - if all you have is full-screen mode, provide a View menu containing only Enter/Exit Full Screen.
- **MBR-15** **Each show/hide item's title must reflect the current state** - "Show Toolbar" when hidden, "Hide Toolbar" when visible.
- **MBR-16** Standard items: Show/Hide Tab Bar, Show All Tabs / Exit Tab Overview, Show/Hide Toolbar, Customize Toolbar, Show/Hide Sidebar, Enter/Exit Full Screen.
- **MBR-17** **The View menu never contains items for navigating between or managing specific windows** - those are the Window menu's job.

**App-specific menus**
- **MBR-18** **Provide app-specific menus for custom commands.** People look in the menu bar for app-specific commands, especially on first use.
- **MBR-19** **Reflect the app's hierarchy** in the menu order (Mail lists Mailbox, Message, Format - mailboxes contain messages, messages contain formatting).
- **MBR-20** List app-specific menus **most general to least general**; people expect leading menus to be more specialised than trailing ones.

**Window menu**
- **MBR-21** **Provide a Window menu even with only one window**, including **Minimize** and **Zoom** so Full Keyboard Access users can invoke them.
- **MBR-22** Consider items for showing and hiding panels.
- **MBR-23** **Avoid using Zoom to enter or exit full-screen mode** - that's the View menu's job.
- **MBR-24** Standard items: Minimize (Option → Minimize All), Zoom (Option → Zoom All), Show Previous Tab, Show Next Tab, Move Tab to New Window, Merge All Windows, Bring All to Front (Option → Arrange in Front).
- **MBR-25** **List currently open windows in alphabetical order** for easy scanning, and **avoid listing panels or other modal views.**
- **MBR-26** **The Window menu does not customise window appearance or close windows** - View customises, File > Close closes.

**Help menu**
- **MBR-27** Items: Send YourAppName Feedback to Apple, YourAppName Help, then additional items after a separator (registration info, release notes). **Keep the total small** so people aren't overwhelmed when they need help; consider linking additional items from inside your help documentation instead.

**Dynamic menu items** (revealed by holding a modifier)
- **MBR-28** **NEVER make a dynamic menu item the only way to accomplish a task** - it's hidden by default, so it suits shortcuts to advanced actions available elsewhere.
- **MBR-29** Use dynamic items **primarily in menu bar menus**; in contextual or Dock menus they're even harder to discover.
- **MBR-30** **Require only a single modifier key.** More than one is physically awkward and reduces discoverability. (macOS sizes a menu to hold the widest item including dynamic items.)

**iPadOS differences**

| | iPadOS | macOS |
|---|---|---|
| Menu bar visibility | Hidden until revealed | Visible by default |
| Horizontal alignment | Centred | Leading side |
| Menu bar extras | Not available | System default and custom |
| Window controls | In the menu bar when the app is full screen | Never in the menu bar |
| Apple menu | Not available | Always available |
| App menu | About, Services and app visibility items not available | Always available |

- **MBR-31 (iPadOS)** **Because the menu bar is often hidden in full screen, every function must be reachable through the app's own UI.** Always offer another way to do anything assigned to a dynamic menu item, since those need a hardware keyboard.
- **MBR-32 (iPadOS)** For tab-style navigation, **consider adding each tab as an item in the View menu.**
- **MBR-33 (iPadOS)** **Consider grouping items into submenus to conserve vertical space** - iPad menu rows are taller than Mac rows so they're easier to tap.

**Menu bar extras (macOS)**
- **MBR-34** Consider a symbol (SF Symbols or custom) to represent your extra.
- **MBR-35** **Display a menu, not a popover**, when people click it - unless the functionality is genuinely too complex for a menu.
- **MBR-36** **Let people, not your app, decide whether your extra appears in the menu bar** - typically through a setting in your settings window.
- **MBR-37** **NEVER rely on the presence of menu bar extras.** The system hides and shows them regularly and you can't predict their location or which others are present.

### 5.30 Pop-up buttons

- **PUB-1** Use a pop-up button for a **flat list of mutually exclusive options or states.** Not for: offering a list of actions, multiple selection, or submenus.
- **PUB-2** **Provide a useful default selection.**
- **PUB-3** **Give people a way to predict the options without opening it** - an introductory label, or a button label describing the effect.
- **PUB-4** Use one when space is limited and you don't need all options visible all the time.
- **PUB-5** Include a **Custom** option where it avoids cluttering the interface with rarely needed controls.
- **PUB-6 (iPadOS)** Within a popover or modal view, **consider a pop-up button instead of a disclosure indicator** for a list item's options, so people choose without navigating to a detail view.

### 5.31 Pull-down buttons

- **PDB-1** Use a pull-down button for **commands or items directly related to the button's action** - an Add button whose menu specifies what to add, a Sort button whose menu picks the attribute, a Back button that offers specific locations.
- **PDB-2** **NEVER put all of a view's actions in one pull-down button.** Primary actions must be easily discoverable, not hidden behind an extra interaction.
- **PDB-3** **List a minimum of three items** so the extra interaction feels worthwhile.
- **PDB-4** Display a menu title **only if it adds meaning** - usually the button content plus descriptive items is enough.
- **PDB-5** **Mark destructive items (menus use red text) and ask people to confirm their intent.**
- **PDB-6** Include an icon with an item when it clarifies meaning - displayed after the label.
- **PDB-7 (iOS, iPadOS)** A **More** pull-down button helps where space is constrained but **hinders discoverability** - weigh that.

### 5.32 Activity views / share sheets (iOS, iPadOS)

- **ACT-1** **NEVER duplicate common actions the activity view already provides** - a second Print action is confusing because people can't tell yours from the system's.
- **ACT-2** Use an SF Symbol to represent a custom activity.
- **ACT-3** **Write a succinct, descriptive title for each custom action.** Long titles wrap and may truncate.
- **ACT-4** **Exclude tasks that don't apply** to the current context. (You can't reorder system-provided tasks.)
- **ACT-5** **Use the Share button to display an activity view** - that's where people expect it.
- **ACT-6** For a share extension, **prefer the system-provided composition view.**
- **ACT-7** **Streamline and limit interaction** - a few steps at most.
- **ACT-8** **Avoid placing a modal view above your extension**, which is already in a modal view.
- **ACT-9** **Use your main app to report progress on a lengthy operation** - the activity view dismisses immediately when the task completes.

### 5.33 Edit menus

- **EDT-1** **Prefer the system-provided edit menu.** A custom menu presenting the same commands is redundant and confusing.
- **EDT-2** Let people reveal it with the system interactions they know - touch and hold on a touchscreen, secondary click with a trackpad or keyboard.
- **EDT-3** **Offer only commands relevant to the current context**, removing or dimming the rest - don't show Copy or Cut with nothing selected.
- **EDT-4** **List custom commands near the relevant system-provided ones** to preserve the expected ordering.
- **EDT-5** **Let people select and copy non-editable text** where it makes sense - an image caption, a status.
- **EDT-6** **Support undo and redo.** An edit menu never confirms before acting, so undo is the recovery path.
- **EDT-7** **In general, avoid other controls that duplicate edit menu functions.**
- **EDT-8** Use verbs or short verb phrases for custom command labels.
- **EDT-9 (iOS, iPadOS)** **Your edit menu must work well in both styles** - the compact horizontal style appears for Multi-Touch gestures, the vertical style for a keyboard or pointing device. Adjust placement as needed; the default is above or below the insertion point or selection depending on available space.

### 5.34 Text views, image views, web views

- **TVW-1** Use a text view for text that's **long, editable, or in a special format.**
- **TVW-2** **Keep text legible** even when using multiple fonts, colours and alignments creatively.
- **TVW-3** **Make useful text selectable** - an error message, a serial number, an IP address.
- **TVW-4 (iOS, iPadOS)** Show the appropriate keyboard type.
- **IVW-1** Use an image view when the **primary purpose is simply to display an image.** To make an image interactive, **configure a system button to display the image** rather than adding button behaviour to an image view.
- **IVW-2** **To display an icon, use a symbol or interface icon, not an image view.**
- **IVW-3** **Take care overlaying text on images** - it reduces both image clarity and text legibility.
- **IVW-4** **Use a consistent size for all images in an animated sequence**, pre-scaled to fit the view so the system doesn't scale them.
- **IVW-5 (macOS)** For an editable image view use an **image well**; for a clickable image use an **image button**.
- **WVW-1** Support forward and back navigation where appropriate - **it isn't available by default.**
- **WVW-2** **NEVER use a web view to build a web browser.** Brief in-app access to a website is fine; Safari is the primary way people browse.

### 5.35 Gauges, page controls, status bars

- **GAU-1** Write succinct labels describing the **current value and both endpoints** - VoiceOver reads the visible labels.
- **GAU-2** Consider a gradient fill that communicates the gauge's purpose (red to blue for hot to cold).
- **GAU-3 (macOS)** Capacity indicators come in **continuous** (translucent track filled with a solid bar) and **discrete** (a row of equally sized segments). **Prefer continuous for large ranges**, where discrete segments become too small to be useful. Default fill is green; change it to flag significant parts of the range.
- **PGC-1** Use page controls **only for movement through an ordered list of pages** - never for hierarchical or non-sequential relationships.
- **PGC-2** **Centre a page control horizontally near the bottom** of the view or window.
- **PGC-3** **Don't display too many** page indicators, even though the control can handle any number.
- **PGC-4** Custom indicator images must be **simple and clear** - no complex shapes, no negative space, no text, no inner lines, all of which turn muddy at small sizes.
- **PGC-5** Customise the default indicator only when it enhances meaning, and **use no more than two different indicator images** in one control.
- **PGC-6** **Avoid colouring indicator images** - custom colours reduce the contrast that identifies the current page and keeps the control visible.
- **PGC-7 (iOS, iPadOS)** **Avoid animating page transitions during scrubbing** - people scrub fast and the animation causes lag and visual flashes. Background styles: **automatic** (background only during interaction - use when the control isn't the primary navigation), **prominent** (always - only when it is the primary navigation), **minimal** (never - when you only need to show position). **Avoid supporting the scrubber with the minimal style**, which gives no visual feedback.
- **STB-1 (iOS, iPadOS)** **Obscure content under the status bar** - its background is transparent by default.
- **STB-2** Consider temporarily hiding the status bar for full-screen media.
- **STB-3** **NEVER permanently hide the status bar** - people then have to leave your app to check the time or their Wi-Fi.

### 5.36 macOS-only structural components

- **TBV-1 (macOS)** **Tab views** present closely related areas of content with a strong visual indication of enclosure. **Controls in a pane must affect content only in the same pane** - panes are mutually exclusive and fully self-contained. **Label each tab to describe its pane's contents. Avoid a pop-up button for switching tabs** (two interactions instead of one). **Avoid more than six tabs.** **Inset the tab view with a margin of window body on all sides.**
- **OTL-1 (macOS)** **Outline views**: use a table instead when data isn't hierarchical. **Expose hierarchy in the first column only.** Descriptive column headings, noun phrases, title-style capitalisation, **no trailing colon.** Let people click headings to sort, resize columns, and easily expand or collapse containers. **Retain people's expansion choices** for next time. Consider alternating row colours in multi-column outline views. Consider a **centred ellipsis** rather than clipping cell text, because it preserves the beginning and end. Consider a search field in the toolbar for lengthy outline views.
- **PNL-1 (macOS)** **Panels** give quick access to controls or information about the content being worked on; an **inspector** panel shows the current selection's details and updates automatically. **Prefer simple adjustment controls** - avoid controls needing typing or item selection. **Write a brief title describing the purpose** (a panel needs a title bar so people can position it). Bring all open panels to the front when the app becomes active. **Avoid listing panels in the Window menu's documents list** (show/hide commands are fine). **In general, don't make a panel's minimize button available.** Refer to panels **by title without the word "panel"** in menus - "Show Fonts", "Show Colors", "Show Inspector".
- **PNL-2 (macOS)** **HUD panels: prefer standard panels.** A HUD makes sense only in a media-oriented app presenting movies, photos or slides; when a standard panel would obscure essential content; or when you don't need controls (most system controls don't match a HUD's appearance). **Maintain one panel style across mode changes. Use colour sparingly. Keep HUDs small.**
- **CMB-1 (macOS)** **Combo boxes**: populate the field with a meaningful default from the list; use an introductory label with **title-style capitalisation ending in a colon**; provide relevant choices as well as custom entry; **keep list items no wider than the text field.**
- **TKF-1 (macOS)** **Token fields**: add a context menu with options or information about a token; provide additional ways to convert text into tokens (a comma does it by default); consider customising the delay before suggestions appear (immediate by default).
- **CLW-1** **Colour wells**: use the system-provided colour picker for a familiar experience and a colour set people can reach from any app.

---

## 6. Interaction patterns - the UX rules

### 6.1 Launching

- **LNC-1** **Launch instantly.** People sometimes don't want to wait more than a couple of seconds.
- **LNC-2** **Restore the previous state on restart** so people continue where they left off. Never make them retrace steps.
- **LNC-3 (iOS, iPadOS)** Provide a **launch screen** - the system shows it the moment the app starts and replaces it with your first screen.
- **LNC-4** **Downplay the launch experience.** A launch screen is not onboarding, not a splash screen, and **not an opportunity for artistic expression.**
- **LNC-5** **Design the launch screen to be nearly identical to your first screen.** Elements that look different cause an unpleasant flash at the handoff.
- **LNC-6** **NEVER include text on a launch screen**, even if the first screen has text - launch screen content doesn't change, so it can't be localised.
- **LNC-7** **NEVER advertise on the launch screen.** It is not a branding opportunity.
- **LNC-8** If you need a **splash screen**, show it at the beginning of the onboarding flow instead.
- **LNC-9 (iOS, iPadOS)** Launch in the device's current orientation if you support both.

### 6.2 Onboarding

- **ONB-1** Ideally people understand the app just by using it. If onboarding is necessary, make it **fast, fun, and optional.** Onboarding happens **after** launching, not as part of it.
- **ONB-2** **Teach through interactivity.** People grasp and retain better by doing the task than by reading about it.
- **ONB-3** **Consider context-specific tips instead of a single onboarding flow**, so people learn while making progress.
- **ONB-4** If a prerequisite flow is unavoidable, make it **brief and enjoyable, requiring no memorisation.**
- **ONB-5** Make a separate tutorial optional; **if people skip it on first launch, NEVER present it again** - but keep it easy to find later.
- **ONB-6** **Keep onboarding focused on your experience.** People don't need to learn how to use the system or the device.
- **ONB-7** **NEVER let large downloads hinder onboarding.**
- **ONB-8** **NEVER display licensing details in onboarding.** Let the App Store show agreements and disclaimers before download.
- **ONB-9** **Postpone non-essential setup and customisation.** Provide reasonable defaults so most people can start immediately.
- **ONB-10** If the app needs private data or resources to function at all, **integrate the permission request into onboarding**, where you can show why it's needed and what people get.
- **ONB-11** **Let people experience the app before prompting for ratings or purchases.**

### 6.3 Loading

- **LOD-1** **Show something as soon as possible.** A blank wait reads as a problem with the app.
- **LOD-2** **Let people do other things while content loads** - load in the background.
- **LOD-3** If loading is unavoidably long, **give people something interesting to look at** - hints, tips, new features.
- **LOD-4** Download large assets in the background to improve installation and launch time.
- **LOD-5** **Clearly communicate that content is loading and how long it might take.**

### 6.4 Feedback

Feedback communicates: current status; the success or failure of an important task; a warning about negative consequences; an opportunity to correct a mistake.

- **FDB-1** **Match the significance of the information to the way it's delivered.** Status information usually belongs somewhere passive, where people can see it when they need it.
- **FDB-2** **Make all feedback accessible**, delivered in more than one way.
- **FDB-3** **Integrate status feedback into the interface near the items it describes**, so people get it without leaving their context.
- **FDB-4** **Use alerts only for critical, ideally actionable information** - they disrupt by design.
- **FDB-5** **Warn people when an action causes data loss that is unexpected and irreversible. NEVER warn when data loss is the expected result of their action.**
- **FDB-6** Confirm that a significant action completed - a successful payment, for instance.
- **FDB-7** **Show when a command can't be carried out and help people understand why.**

### 6.5 Modality

Modality presents content in a separate, dedicated mode that prevents interaction with the parent view and **requires an explicit action to dismiss.**

- **MOD-1** **Present content modally only when there's a clear benefit** - it takes people out of their context.
- **MOD-2** **Keep modal tasks simple, short and streamlined.** If a modal task is too complicated people lose track of the task they suspended, especially when the modal view obscures the previous context.
- **MOD-3** **NEVER create a modal experience that feels like an app within your app.** A hierarchy of views inside a modal task makes people forget how to retrace their steps.
- **MOD-4** Consider a **full-screen modal style** for in-depth content or a complex task - video, photos, camera views, marking up a document, editing a photo.
- **MOD-5** **Always give people an obvious way to dismiss a modal view**, following the platform conventions they know.
- **MOD-6** **Get confirmation before closing a modal view when closing could lose user-generated content** - whether people used a gesture or a button.
- **MOD-7** **Make the modal view's task easy to identify.**
- **MOD-8** **Let people dismiss one modal view before presenting another.** Multiple simultaneous modals create clutter and make the app seem scattered.

### 6.6 Offering help

- **HLP-1** Let the app's tasks determine the kind of help people need.
- **HLP-2** Use relevant, consistent language and images, always appropriate to the current context.
- **HLP-3** **Make all help content inclusive.**
- **HLP-4** **NEVER bloat help content by explaining how standard components or patterns work.** Describe the specific action or task the standard element performs *in your app.*
- **HLP-5** **Tips**: use a **popover tip** to preserve content flow, an **inline tip** to keep surrounding information visible.
- **HLP-6** Use tips for **simple features** that are easy to describe and take a few steps.
- **HLP-7** Make tips **short, actionable and engaging.**
- **HLP-8** **Define rules so tips reach the intended audience** - not everyone benefits from every tip.
- **HLP-9** If an image or symbol is associated with the feature, include it and **prefer the filled variant** - but **don't repeat the same image in both the tip and the UI** when the tip connects directly to it.
- **HLP-10** Use buttons in a tip to direct people to settings or more information.
- **HLP-11 (macOS)** **Tooltips**: describe only the control the person indicated interest in - not nearby controls or a larger task. **Begin with a verb** ("Restore default settings"). **Avoid repeating the control's name.** **Limit content to 60–75 characters** (localisation changes length). **Use sentence case.** Consider context-sensitive tooltips with different text per state.

### 6.7 Entering data

- **ENT-1** **Get information from the system whenever possible.** Never ask people to type what you can obtain from settings or with permission.
- **ENT-2** **Be clear about the data you need** - a prompt in the field ("username@company.com") or an introductory label ("Email"). **Prefill fields with reasonable defaults** to reduce decisions and speed entry.
- **ENT-3** Use a **secure text-entry field** for sensitive data.
- **ENT-4** **NEVER prepopulate a password field.** Always ask people to enter their password or use biometric or keychain authentication.
- **ENT-5** **Offer choices instead of requiring text entry where possible** - choosing from a list is easier and faster than typing even with a keyboard handy.
- **ENT-6** **Let people provide data by dragging and dropping or pasting.**
- **ENT-7** **Validate field values dynamically.** People get frustrated correcting mistakes after filling a long form.
- **ENT-8** Make it clear that required data is required - e.g. **keep the Next or Continue button unavailable until the required fields are filled.**

### 6.8 Searching

- **SCH-1** **If search is important, give it a primary position.**
- **SCH-2** **Aim to make all your content searchable through a single location.** People appreciate one clearly identified place to find anything.
- **SCH-3** **Clearly display the current scope of a search** - descriptive placeholder text, a scope bar, or a title.
- **SCH-4** Provide suggestions: recent searches before typing, predictive suggestions while typing.
- **SCH-5** **Take privacy into account before displaying search history** - people may not want it visible to others.
- **SCH-6** Make your content searchable in **Spotlight** by indexing it with descriptive metadata; define metadata for custom file types with a Spotlight File Importer plug-in; implement a **Quick Look generator** for custom file types.
- **SCH-7** **Prefer the system-provided open and save views** - they include a built-in search field that searches the whole system.

### 6.9 Settings

- **SET-1** **Provide defaults that give the best experience to the largest number of people.**
- **SET-2** **Minimise the number of settings.** Too many makes the experience less approachable and any one setting harder to find.
- **SET-3** Make settings available where people expect - **Command-comma** opens app settings when a keyboard is connected; in a game, players often use **Esc**.
- **SET-4** **NEVER use settings to ask for setup information you can get another way** - detect the connected controller, detect Dark Mode.
- **SET-5** **Respect systemwide settings and NEVER duplicate them.** People manage accessibility accommodations, scrolling behaviour and authentication methods in the system Settings app and expect every app to follow.
- **SET-6** Put **general, infrequently changed** settings in your custom settings area - people must suspend what they're doing to get there.
- **SET-7** **Keep task-specific options in the screens they affect**, where they're discoverable and convenient - showing/hiding parts of the current view, reordering, filtering.
- **SET-8** Add only the **most rarely changed** options to the system Settings app, and provide a button that opens it directly.
- **SET-9 (macOS)** **Put a Settings item in the App menu. Avoid adding a settings button to a window's toolbar** - it costs space needed for frequently used commands.
- **SET-10 (macOS)** **Dim a settings window's minimise and maximise buttons.**
- **SET-11 (macOS)** Use a **non-customisable toolbar that stays visible and always indicates the active button.**
- **SET-12 (macOS)** **Update the window title to the visible pane.** With a single pane, title it "*App Name* Settings".
- **SET-13 (macOS)** **Restore the most recently viewed pane** when the window reopens.

### 6.10 Undo and redo

- **UND-1** **Help people predict the results of undo and redo.** On iPhone, describe the result in the shake alert and let people perform or cancel it.
- **UND-2** **Show the results of an undo or redo** - the affected content may no longer be visible.
- **UND-3** **Let people undo multiple times.** Avoid unnecessary limits.
- **UND-4** Consider letting people revert a **batch** of discrete but related actions at once - e.g. incremental adjustments to one property - instead of undoing each one.
- **UND-5** **Provide undo and redo buttons only when necessary.** People expect the system-supported ways: the macOS Edit menu, keyboard shortcuts on Mac or iPad, shaking an iPhone.
- **UND-6 (iOS, iPadOS)** **NEVER redefine the standard undo/redo gestures** - three-finger swipe, shake. Describe the operation briefly and precisely; the alert title automatically prefixes "Undo " or "Redo ".
- **UND-7 (macOS)** Put undo and redo **at the top of the Edit menu** and support **Command-Z** and **Shift-Command-Z**.

### 6.11 Drag and drop

- **DND-1** **Support drag and drop throughout the app as much as possible.** Most people are familiar with it and try it everywhere.
- **DND-2** **Always offer alternative ways to accomplish drag-and-drop actions** - it's inconvenient or impossible for some people.
- **DND-3** **Move vs copy**: in general a **move** makes sense when source and destination containers are the same; a **copy** when they differ.
- **DND-4** Support **multi-item** drag and drop where it makes sense.
- **DND-5** **Let people undo a drag-and-drop operation.**
- **DND-6** Offer **multiple versions of dragged content, ordered highest to lowest fidelity**, so the destination can take the best it accepts.
- **DND-7** Consider **spring loading** - activating a control by dragging content over it.
- **DND-8** **Display a drag image as soon as people drag about three points.** A translucent representation of the content works well.
- **DND-9** Modify the drag image to help people predict the result - e.g. expanding a photo to its default size in the document.
- **DND-10** **Show whether a destination can accept the content**: an insertion point or highlight when it can; **no feedback, or an explicit "not allowed" image such as `circle.slash`**, when it can't.
- **DND-11** **Give visual feedback on an invalid or failed drop** - move the item back to its source, or scale it up and fade it out so it appears to evaporate rather than land.
- **DND-12** Scroll the destination's contents automatically when people drag an item over a long scrolling container.
- **DND-13** **Pick the richest version of dropped content your app can accept.**
- **DND-14** **Extract only the relevant portion** of dropped content - dropping a contact into a recipient field yields the name and email address, not the postal address.
- **DND-15** **Check for the Option key at drop time** - holding Option forces a same-container drag to behave like a copy.
- **DND-16** Show a progress indicator when dropped content needs time to transfer, and show that a task has begun when a drop initiates one.
- **DND-17** **Apply appropriate styling to dropped text** - when source and destination support the same styles, preserve font, typeface, size and other attributes.
- **DND-18** **Maintain the content's selection state in the destination after a drop**, updating the source as needed, so people can act on it immediately.
- **DND-19 (iPadOS)** Let people add items to an in-progress drag session, and perform multiple simultaneous drags.
- **DND-20 (macOS)** Let people drag content into the Finder, **in a format your app can open later.**
- **DND-21 (macOS)** **Let people drag selected content from an inactive window without first activating it** (a "background selection", which looks different from an active selection), and **let them drag an individual unselected item without affecting an existing background selection.**
- **DND-22 (macOS)** Consider a **badge** - a small filled oval with a number - during multi-item drags, and change the pointer (copy, drag link, disappearing item, operation not allowed) to indicate the outcome.
- **DND-23 (macOS)** **Let people select and drag with a single motion** - no forced pause between selecting and dragging, unless they're selecting multiple items.

### 6.12 Multitasking

- **MUL-1** **Every app needs to work well with multitasking**, with rare exceptions (some games). **Always be prepared to save and restore context**, because you don't know when people will switch away.
- **MUL-2** **Pause activities requiring attention or active participation when people switch away** - games, media playback.
- **MUL-3** **Respond smoothly to audio interruptions**: pause **indefinitely** for primary audio interruptions (music, podcasts, audiobooks); **temporarily lower the volume or pause** for short interruptions (GPS directions) and restore afterward.
- **MUL-4** **Finish user-initiated tasks in the background** - a download or a video export must complete even if people switch away.
- **MUL-5** **Use notifications sparingly.**
- **MUL-6 (iPadOS)** People run apps **full screen** (switched via the app switcher) or **windowed** (freely resizable, with system window controls for tiling, full screen, minimise and close). Video and FaceTime can play in Picture in Picture over either. **[27]**
- **MUL-7 (iPadOS)** **Apps don't control multitasking configurations and get no indication of the one people chose** - so adapt gracefully to any screen size.

### 6.13 Going full screen (iOS, iPadOS, macOS)

- **FSC-1** Support full-screen mode where it suits the experience.
- **FSC-2** **Adjust your layout in full screen, but NEVER programmatically resize your window.**
- **FSC-3** **Keep essential features and controls accessible** so people can finish the task without exiting - a full-screen media experience keeps playback controls persistently available or easy to reveal.
- **FSC-4 (iPadOS, macOS)** **Except in games, let people reveal the Dock** while in full screen.
- **FSC-5** **Help people resume where they left off** after switching away - pause a game or slideshow automatically.
- **FSC-6** **Let people choose when to exit full-screen mode.** People don't expect it to end automatically.
- **FSC-7** Prioritise content by **temporarily** hiding toolbars and navigation controls when content is the primary focus.
- **FSC-8 (iOS, iPadOS)** Consider **deferring system gestures** to prevent accidental exits.
- **FSC-9 (macOS)** **Use the system-provided full-screen experience.** **In a game, NEVER change the display mode when players go full screen** - people expect to control their display mode and changing it doesn't improve performance. **Always let people choose when to enter full screen** - the window's Enter Full Screen button, the View menu item, or **Control-Command-F**.

### 6.14 File management

- **FIL-1** Use app menus and keyboard shortcuts to create and open documents (iPadOS and macOS especially).
- **FIL-2** If you must build a custom file browser, **support people's existing understanding of the platform's file system.**
- **FIL-3** **Help people be confident their work is always preserved unless they cancel or delete it. In general, avoid making people take an explicit action to save.**
- **FIL-4** **Hide file extensions by default but let people view them**, and reflect that choice in every save and open interface.
- **FIL-5** **Use a Quick Look viewer** so people can preview files your app can't open, and **implement a Quick Look generator** for custom file types so the Finder, Files and Spotlight can preview them.
- **FIL-6 (iOS, iPadOS)** The **document launcher** (iOS/iPadOS 18+) has a **title card** (app title plus two app-specific buttons), a **background image** with optional **accessories**, and a **sheet** containing a file browser. Assign the title card's buttons to your most important functions - the primary button typically creates a new document. **Provide a background clearly distinct from the accessories and title card.** **Be mindful of accessory placement** - accessories can sit in front of and behind the card for depth, but the app name and both buttons must stay clearly visible. **Use animation sparingly.**
- **FIL-7 (iOS, iPadOS)** In a **file provider extension**, display only documents appropriate to the current context (a PDF editor sees only PDFs), let people choose a destination when exporting or moving, and **avoid a custom top toolbar** - the modal view already has one.
- **FIL-8 (macOS)** **Use the default file browser unless you have an important reason not to.** Offer "open recent" as well as "open". Provide a save interface for changing name, format and location (a new document is "Untitled" until named). Consider a custom accessory view in the Save dialog.
- **FIL-9 (macOS)** People can **turn autosaving off** ("Ask to keep changes when closing documents" in Desktop & Dock settings). **When autosaving is off, show unsaved changes with a dot on the window's close button and next to the document's name in the Window menu.**
- **FIL-10 (macOS)** A **Finder Sync extension** can show sync-status badges, custom contextual menu items and custom toolbar buttons in the Finder.

---

## 7. Input rules

### 7.1 Gestures

- **GST-1** **Give people more than one way to interact.** Many prefer or need voice, keyboard or Switch Control.
- **GST-2** **Respond to gestures consistently with people's expectations** - most gestures should work the same regardless of context.
- **GST-3** **Handle gestures as responsively as possible**, with immediate feedback.
- **GST-4** **Indicate when a gesture isn't available**, or people think the app has frozen or that they're performing the gesture wrong.
- **GST-5** **Add custom gestures only when necessary** - for specialised, frequent tasks not covered by existing gestures. A custom gesture must be: **discoverable, straightforward to perform, distinct from other gestures, and never the only way to perform an important action.**
- **GST-6** **Make custom gestures easy to learn**, with moments in the app that teach them; test in real use scenarios.
- **GST-7** **Shortcut gestures supplement standard gestures - they NEVER replace them.** People still need simple, familiar navigation even if it costs an extra tap or two.
- **GST-8** **NEVER conflict with gestures that access system UI.**
- **GST-9** Allow simultaneous recognition of multiple gestures only when it genuinely enhances the experience - rarely useful outside games.

**Standard gestures and their common actions**

| Gesture | Common action |
|---|---|
| Tap | Activate a control; select an item |
| Swipe | Reveal actions and controls; dismiss views; scroll |
| Drag | Move a UI element |
| Touch (or pinch) and hold | Reveal additional controls or functionality |
| Double tap | Zoom in; zoom out if already zoomed in |
| Zoom | Zoom a view; magnify content |
| Rotate | Rotate a selected item |

**Additional gestures people expect on iOS and iPadOS**

| Gesture | Common action |
|---|---|
| Three-finger swipe | Undo (left) / redo (right) |
| Three-finger pinch | Copy selected text (in) / paste (out) |
| Four-finger swipe (iPadOS only) | Switch between apps |
| Shake | Undo / redo |

### 7.2 Physical keyboards

- **KBD-1** **Support Full Keyboard Access** (iOS, iPadOS, macOS) so people can navigate and activate windows, menus, controls and system features with the keyboard alone.
- **KBD-2 (iPadOS)** iPadOS supports keyboard navigation in **text fields, text views and sidebars**, and offers APIs for collection views and custom views. **Avoid supporting keyboard navigation for controls** - buttons, segmented controls, switches. Let Full Keyboard Access activate those, reach every on-screen component, and perform gesture-based interactions like drag and drop.
- **KBD-3** **Respect standard keyboard shortcuts. In general, NEVER repurpose a standard shortcut for a custom action.**
- **KBD-4** **Define custom shortcuts only for the most frequently used app-specific commands.** Too many new shortcuts make an app seem hard to learn.
- **KBD-5** **Use modifier keys as people expect** - Command while dragging moves items as a group; Shift while drag-resizing constrains to the aspect ratio.
- **KBD-6** Modifier key usage:
  - **Command** - prefer it as the **main** modifier in a custom shortcut.
  - **Shift** - prefer it as a **secondary** modifier complementing a related shortcut.
  - **Option** - use **sparingly**, for less-common commands or power features.
  - **Control** - **avoid using Control as a modifier.** The system uses it for many systemwide features and shortcuts.
- **KBD-7** **List modifier keys in this order: Control, Option, Shift, Command.**
- **KBD-8** **Avoid adding Shift to a shortcut that uses the upper character of a two-character key** - people already know Shift is needed, so list the upper character alone.
- **KBD-9** **Let the system localise and mirror your shortcuts.** It adapts them to the connected keyboard and mirrors them automatically for right-to-left layouts. (Note that some languages need modifier keys to produce certain characters - on a French keyboard, Option-5 gives "{".)
- **KBD-10** **NEVER create a new shortcut by adding a modifier to an existing shortcut for an unrelated command.** Shift-Command-Z for something unrelated to redo is confusing.

**The standard shortcuts people expect everywhere** - the load-bearing subset:

| Shortcut | Action |
|---|---|
| Command-A / Shift-Command-A | Select all / deselect all |
| Command-X / C / V | Cut / copy / paste |
| Shift-Command-V | Paste as (e.g. Paste as Quotation) |
| Option-Command-V | Apply the style of one object to the selection |
| Option-Shift-Command-V | Paste and match the surrounding style |
| Command-Z / Shift-Command-Z | Undo / redo |
| Command-B / I / U | Bold / italic / underline |
| Command-N / O / S / P / W / Q | New / open / save / print / close window / quit |
| Shift-Command-S | Duplicate the active document, or Save As |
| Shift-Command-P | Page Setup |
| Shift-Command-W / Option-Command-W | Close a file and its windows / close all the app's windows |
| Command-F | Open a Find window |
| Command-G / Shift-Command-G | Find next / find previous |
| Command-E | Use the selection for a find operation |
| Option-Command-F | Jump to the search field |
| Command-comma | Open the app's settings window |
| Command-question mark | Open the app's Help menu |
| Command-M / Option-Command-M | Minimise the active window / minimise all the app's windows |
| Command-H / Option-Command-H | Hide this app's windows / hide all other apps' windows |
| Command-left bracket / right bracket / pipe | Left-align / right-align / centre-align a selection |
| Command-hyphen / Shift-Command-equals | Decrease / increase the size of the selection |
| Command-period or Esc | Cancel the current operation |
| Control-Command-F | Enter full screen |
| Command-grave / Shift-Command-grave | Next / previous window in the frontmost app |
| Command-semicolon / Command-colon | Find misspelled words / show the Spelling window |
| Command-T / Option-Command-T | Show the Fonts window / show or hide a toolbar |
| Command-I / Option-Command-I | Info window / inspector window |
| Command-J | Scroll to a selection |
| Control-Command-D | Show the definition of the selected word |
| Option-Command-D | Show or hide the Dock |
| Shift-Command-3 / Shift-Command-4 | Capture the screen / a selection to a file (add Control to send it to the Clipboard) |
| Control-F1 | Toggle Full Keyboard Access |
| Control-F2 / F3 / F4 / F5 / F6 | Move focus to the menu bar / Dock / active window / toolbar / first panel |
| Command-F5 | Turn VoiceOver on or off |
| Option-Command-8 | Turn screen zooming on or off |
| Command-Space | Show or hide Spotlight |
| Command-Tab / Shift-Command-Tab | Move forward / backward through open apps |
| Shift-Tab | Navigate controls in reverse |
| Control-Tab / Control-Shift-Tab | Next / previous group of controls in a dialog |
| Shift-arrow, Option-Shift-arrow, Shift-Command-arrow | Extend the selection by character, by word, and by semantic unit |
| Control-arrow | Move focus to another value or cell within a view such as a table |
| Option-Command-Esc | Open the Force Quit dialog |
| Control-Space / Control-Option-Space | Toggle between the last two input sources / next input source |

### 7.3 Pointing devices

- **PTR-1** **Be consistent when responding to mouse and trackpad gestures.**
- **PTR-2** **NEVER redefine systemwide trackpad gestures** - even a game must leave the Dock and Mission Control gestures working.
- **PTR-3** **Provide a consistent experience across gestures, eyes, pointing device and keyboard.** People move fluidly between inputs and don't want to learn different interactions per mode or per app.
- **PTR-4** Let people **use the pointer to reveal and hide controls that minimise or fade out** - holding the pointer over the minimised Safari toolbar in iPadOS reveals it, and it minimises again when the pointer moves away.
- **PTR-5** **Modifier-key behaviour must be identical across touch and pointer.** If Option-drag duplicates an object, it does so either way.
- **PTR-6 (iPadOS)** The pointing system **adds to touch, it doesn't replace it.** Three content effects, and what each is for:
  - **Highlight** - a translucent rounded rectangle behind a control, with gentle parallax. Use for a **small element with a transparent background.**
  - **Lift** - parallax plus elevation: the pointer fades out as the element scales up, with a shadow below and a soft specular highlight on top. Use for a **small element with an opaque background.**
  - **Hover** - generic; you apply custom scale, tint or shadow. Use for **large elements.**
- **PTR-7 (iPadOS)** **Pointer magnetism** pulls the pointer toward an element as it enters the element's hit region (which extends beyond the visible boundary), and toward an element's centre when people flick at it. The system applies magnetism to **lift** and **highlight** elements and to **text-entry areas** (where it stops people skipping lines during selection) - but **not to hover**, because a hover element doesn't transform the pointer and magnetism there would feel like losing control.
- **PTR-8 (iPadOS)** **Support the system-provided content effects and pointer appearances** for standard buttons and text-entry areas.
- **PTR-9 (iPadOS)** **Add padding around interactive elements to create comfortable hit regions**, and **create contiguous hit regions for custom bar buttons** - a gap between adjacent buttons' hit regions causes a distracting flicker as the pointer reverts to its default shape in between.
- **PTR-10 (iPadOS)** **Specify the corner radius of a non-standard element that receives the lift effect**, because the pointer transforms to match the element's shape as it fades out.
- **PTR-11 (iPadOS)** **Prefer system pointer effects for custom elements that behave like standard ones.** Use pointer effects consistently throughout the app, and **avoid gratuitous pointer and content effects** - people notice every change and expect it to be useful.
- **PTR-12 (iPadOS)** **Keep custom pointer shapes simple.** Consider custom annotations that provide useful information (X and Y values over a graphing area), but **NEVER display instructional text with a pointer** - it makes an app seem complicated and hard to use.
- **PTR-13 (iPadOS)** Consider the interplay of shadow, scale and element spacing in custom hover effects; **reserve scaling for elements that can grow without crowding their neighbours.**
- **PTR-14 (macOS)** Use the standard pointer styles to communicate interactive state and drag outcomes: **arrow, closed hand, contextual menu, crosshair, disappearing item, drag copy, drag link, horizontal I-beam, open hand, operation not allowed, pointing hand, resize (up, down, left, right, up/down, left/right), vertical I-beam.**
- **PTR-15 (macOS)** Standard interactions people expect (and can turn on or off): primary click, secondary click, scrolling, smart zoom, swipe between pages, swipe between full-screen apps, Mission Control, lookup and data detectors, tap to click, force click (including pressure-sensitive controls), pinch zoom, rotate, Notification Center swipe, App Exposé, Launchpad, Show Desktop.

### 7.4 Focus and selection (iPadOS, macOS)

Focus lets people visually confirm which object their interaction targets. Focusing an item usually selects it too - the exception is when automatic selection would cause a distracting context shift, like opening a new view.

- **FOC-1** **Rely on system-provided focus effects** - they're tuned to feel responsive, fluid and lifelike.
- **FOC-2** **NEVER change focus without people's interaction.** People rely on focus to know where they are.
- **FOC-3** **Be consistent with the platform.** Where Full Keyboard Access already reaches every control, you only need to support focus for **content elements** - list items, text fields, search fields - **not controls** like buttons, sliders and toggles.
- **FOC-4** **In general, use a focus ring for a text or search field and a highlight in a list or collection.** A focus ring works for an item that fills a cell (a photo), but highlighting the whole row is usually easier to read.
- **FOC-5 (iPadOS)** **Tab** moves focus among focus groups (sidebars, grids, app areas); **arrow keys** move among items within a single focus group.
- **FOC-6 (iPadOS)** Two indications: the **halo** (focus ring) effect, whose shape the system infers from the item's shape and which you can customise; and the **highlighted** appearance, where the component's text uses the app's accent colour - which indicates focus but is not technically a focus effect.
- **FOC-7 (iPadOS)** **Focus moves through focus groups in reading order - leading to trailing, top to bottom.** Verify that it does so sensibly in custom views.
- **FOC-8 (iPadOS)** **Set a focus group's primary item.** It receives focus automatically when the group does, so make it the item people are most likely to want.

### 7.5 Apple Pencil and Scribble (iPadOS)

- **PEN-1** **Support the behaviours people intuitively expect from a real marking instrument.**
- **PEN-2** **Let people choose when to switch between Apple Pencil and finger input.** Your controls must respond to Apple Pencil too, so people never have to switch to a finger to activate them.
- **PEN-3** **Let people make a mark the moment Apple Pencil touches the screen.**
- **PEN-4** Respond to what the Pencil senses: **tilt (altitude), force (pressure), orientation (azimuth) and barrel roll.**
- **PEN-5** **Provide visual feedback indicating a direct connection with content** - the Pencil must appear to manipulate what it touches directly and immediately.
- **PEN-6** **Design a great left- AND right-handed experience.** Never place controls where either hand obscures them.
- **PEN-7** **Use hover to help people predict what happens when the Pencil touches the screen** - e.g. a preview of the mark's dimensions and colour.
- **PEN-8** **NEVER use hover to initiate an action.** Hovering is imprecise and people don't think about the actual distance to the display.
- **PEN-9** **Prefer showing a preview value near the middle of a dynamic range** - opacity or flow is hard to depict at the extremes.
- **PEN-10** **Prefer hover previews for Apple Pencil, not for a pointing device** - identical feedback for both is confusing.
- **PEN-11** **Respect people's double-tap settings.** The default toggles between the current tool and the eraser; people may set it to toggle current/previous tool, show/hide the colour picker, or do nothing. Provide a control to choose a custom mode if you offer one.
- **PEN-12** **NEVER use double tap to modify content.** People double-tap accidentally and may not even notice the action happened.
- **PEN-13** **Treat squeeze as a single quick gesture performing a discrete - not continuous - action**; holding or repeating a squeeze is tiring. **Display the result close to the Pencil tip** to strengthen the connection. **Squeeze actions must be non-destructive and easy to undo.** Note that people may configure squeeze to run an App Shortcut instead of your action, and that squeeze works while the Pencil isn't touching the screen, so people may not be looking at the result.
- **PEN-14** **Use barrel roll only to modify marking behaviour**, never for navigation or to reveal controls - unlike double tap and squeeze, barrel roll is naturally related to marking.
- **PEN-15** **Scribble works in every standard text component by default** - text fields, text views, search fields, editable web fields - **except password fields.** Make it available everywhere people might want to enter text.
- **PEN-16** **Avoid distracting people while they write**, and **keep the text field stationary.** Behaviour that's fine for keyboard input - a search field that moves when focused to make room for results - disrupts writing.
- **PEN-17** **Prevent autoscrolling text while people write and edit.** When transcribed text scrolls, people try to avoid writing on top of it.
- **PEN-18** **Give people enough space to write.** A small text field is uncomfortable to write in.
- **PEN-19 (PencilKit)** Canvas colours adjust to Dark Mode automatically, so content created in either mode looks right in both. **In a compact environment, display custom undo and redo buttons** - the tool picker includes them only in a regular environment.

---

## 8. System experiences and account rules

### 8.1 Notifications

A notification gives people **timely, high-value information they can understand at a glance.** You need consent before sending any. Styles: a banner on the Lock Screen, Home Screen or desktop; a badge on the app icon; an item in Notification Center. Communication notifications (a call, a message) get their own interface with contact images and group names instead of the app icon.

- **NTF-1** **Provide concise, informative notifications.**
- **NTF-2** **NEVER send multiple notifications for the same thing**, even if the person hasn't responded - they attend to notifications at their convenience.
- **NTF-3** **NEVER send a notification that tells people to perform a specific task inside your app.** If a simple task can be done without opening the app, offer it as a notification action instead.
- **NTF-4** **Use an alert, not a notification, for an error message.**
- **NTF-5** **Handle notifications gracefully when your app is in the foreground** - they don't appear, but your app still receives the information.
- **NTF-6** **NEVER include sensitive, personal or confidential information in a notification.** You can't predict who is looking at the screen.
- **NTF-7** Create a short title only if it gives context. Keep titles glanceable.
- **NTF-8** Write succinct content: **complete sentences, sentence case, proper punctuation. NEVER truncate your own message** - the system does that when it needs to.
- **NTF-9** **Provide generically descriptive text for when previews are hidden** - people can turn previews off for all apps.
- **NTF-10** **NEVER include your app name or icon in the text.** The system already shows a large app icon at the leading edge (and, in a communication notification, the sender's contact image badged with a small version of your icon).
- **NTF-11** Consider a sound to supplement notifications.
- **NTF-12** **Notification actions**: offer beneficial actions that save time and remove the need to open the app. **NEVER provide an action that merely opens your app** - tapping the notification already does that, so the duplicate clutters the view and confuses people. **Prefer non-destructive actions**; if an action is destructive, give enough context to avoid accidents. Give each action a **simple, recognisable interface icon.**
- **NTF-13** **Use a badge only to show the number of unread notifications.** **NEVER badge numeric information unrelated to notifications** - weather data, dates, stock prices, game scores.
- **NTF-14** **NEVER make badging the only way you communicate essential information.** People can turn it off.
- **NTF-15** **Keep badges up to date** - clear them as soon as people open the corresponding notifications.
- **NTF-16** **NEVER create a custom image or component that mimics a badge.** People who have turned badges off will be frustrated to see what looks like one.

### 8.2 Widgets

A widget appears on the Home Screen and Lock Screen (iPhone, iPad), on the desktop and in Notification Center (Mac), in StandBy and CarPlay, and in the Apple Watch Smart Stack.

**Sizes.** System family: small, medium, large, extra large (extra large is iPad, Mac and Vision Pro only - **not iPhone**). Accessory family: circular, corner, inline, rectangular.

**Appearances (iPhone, iPad Home Screen)**: **light, dark, clear, tinted.** Light and dark are full-colour. On the iPhone and iPad Lock Screen, a widget is **monochromatic with no tint colour.** In StandBy it scales up with the background removed, and below an ambient-light threshold the system renders it with a **monochromatic red tint.**

**Three rendering modes**: **full colour** (system family everywhere; your view colours are untouched), **accented** (background removed and replaced with a tinted colour effect for the tinted appearance, or a **Liquid Glass background for the clear appearance**), **vibrant** (Lock Screen and low-light StandBy; text, images and gauges desaturated and coloured against the background).

- **WDG-1** **Choose simple ideas that relate to your app's main purpose**, with timely content and relevant functionality.
- **WDG-2** **Prefer dynamic information that changes through the day.** A widget whose content never appears to change loses its prominent position.
- **WDG-3** Offer multiple sizes only when each adds value - small usually shows a single piece of information, larger sizes support more layers and actions.
- **WDG-4** **Balance information density.** Sparse layouts make the widget seem unnecessary; dense layouts stop being glanceable.
- **WDG-5** **Display only information directly related to the widget's main purpose.**
- **WDG-6** Use brand elements thoughtfully - colours, typefaces, stylised glyphs - **without overpowering useful information.**
- **WDG-7** **NEVER mirror your widget's appearance inside your app.** An element that looks like the widget but doesn't behave like it confuses people.
- **WDG-8** **Keep the widget up to date**, and **let the system refresh dates and times** rather than spending an update opportunity on them.
- **WDG-9** Use animated transitions to draw attention to data updates.
- **WDG-10** **Offer simple, relevant functionality and reserve complexity for the app.** **NEVER create app-like layouts in a widget.**
- **WDG-11** **A widget interaction must open the app at the right location** - deep link to the details and actions the widget shows, never dump people at the top level.
- **WDG-12** **Standard widget margin: 16 pt for most widgets.** Crowded edges look cluttered.
- **WDG-13** **Coordinate your content's corner radius with the widget's corner radius**, using a container that applies the correct radius.
- **WDG-14** **Prefer the system font, text styles and SF Symbols.**
- **WDG-15** **Display text at 11 pt or larger.**
- **WDG-16** **NEVER rasterise text** - it stops scaling and VoiceOver can't read it. (Widgets support Dynamic Type from Large to AX5 on iOS, iPadOS and visionOS.)
- **WDG-17** **Convey meaning without relying on specific colours** - a widget can be monochromatic, with or without a tint.
- **WDG-18** **Use full-colour images judiciously.** With the tinted or clear appearance the system desaturates them by default.
- **WDG-19** In full-colour mode, support light and dark appearances with semantic system colours. In accented mode, **group components into an accent group and a primary group.** In vibrant mode, **offer enough contrast** (pixel opacity drives the blurred background material effect) and **render images, numbers and text at full opacity.**
- **WDG-20** **Design a realistic preview for the widget gallery**, plus **placeholder content** that helps people recognise your widget while data loads, and a **succinct description.**
- **WDG-21** **Group your widget's sizes together with a single description**, so people don't think each size is a different widget.
- **WDG-22 (iOS, iPadOS)** **Support the Always-On display** - widgets render on the Lock Screen at reduced luminance.
- **WDG-23** **Widgets don't show real-time information. Use a Live Activity for that.**
- **WDG-24 (StandBy)** **Limit rich images and colour as meaning-carriers.** Use the extra space by scaling up and rearranging text so it reads from a distance.

**iOS widget dimensions (portrait screen size → widget size, pt)**

| Screen | Small | Medium | Large | Circular | Rectangular | Inline |
|---|---|---|---|---|---|---|
| 430×932 | 170×170 | 364×170 | 364×382 | 76×76 | 172×76 | 257×26 |
| 428×926 | 170×170 | 364×170 | 364×382 | 76×76 | 172×76 | 257×26 |
| 414×896 | 169×169 | 360×169 | 360×379 | 76×76 | 160×72 | 248×26 |
| 414×736 | 159×159 | 348×157 | 348×357 | 76×76 | 170×76 | 248×26 |
| 393×852 | 158×158 | 338×158 | 338×354 | 72×72 | 160×72 | 234×26 |
| 390×844 | 158×158 | 338×158 | 338×354 | 72×72 | 160×72 | 234×26 |
| 375×812 | 155×155 | 329×155 | 329×345 | 72×72 | 157×72 | 225×26 |
| 375×667 | 148×148 | 321×148 | 321×324 | 68×68 | 153×68 | 225×26 |
| 360×780 | 155×155 | 329×155 | 329×345 | 72×72 | 157×72 | 225×26 |
| 320×568 | 141×141 | 292×141 | 292×311 | - | - | - |

**iPadOS widget dimensions - canvas size (design at this size) and device size (what it renders at)**

| Screen | | Small | Medium | Large | Extra large |
|---|---|---|---|---|---|
| 768×1024 | canvas | 141×141 | 305.5×141 | 305.5×305.5 | 634.5×305.5 |
| | device | 120×120 | 260×120 | 260×260 | 540×260 |
| 744×1133 | canvas | 141×141 | 305.5×141 | 305.5×305.5 | 634.5×305.5 |
| | device | 120×120 | 260×120 | 260×260 | 540×260 |
| 810×1080 | canvas | 146×146 | 320.5×146 | 320.5×320.5 | 669×320.5 |
| | device | 124×124 | 272×124 | 272×272 | 568×272 |
| 820×1180 | canvas | 155×155 | 342×155 | 342×342 | 715.5×342 |
| | device | 136×136 | 300×136 | 300×300 | 628×300 |
| 834×1112 | canvas | 150×150 | 327.5×150 | 327.5×327.5 | 682×327.5 |
| | device | 132×132 | 288×132 | 288×288 | 600×288 |
| 834×1194 | canvas | 155×155 | 342×155 | 342×342 | 715.5×342 |
| | device | 136×136 | 300×136 | 300×300 | 628×300 |
| 954×1373 | both | 162×162 | 350×162 | 350×350 | 726×350 |
| 970×1389 | both | 162×162 | 350×162 | 350×350 | 726×350 |
| 1024×1366 | canvas | 170×170 | 378.5×170 | 378.5×378.5 | 795×378.5 |
| | device | 160×160 | 356×160 | 356×356 | 748×356 |
| 1192×1590 | both | 188×188 | 412×188 | 412×412 | 860×412 |

### 8.3 Controls (iOS, iPadOS, macOS)

A control appears in Control Center (symbol alone at small sizes; symbol, title and value at larger sizes), on the Lock Screen (symbol only), and in the Dynamic Island when assigned to the iPhone Action button.

- **CTL-1** **Offer controls for actions that provide the most benefit without launching the app.**
- **CTL-2** **Update the control when someone interacts with it, when an action completes, or remotely via push** - the state must be accurate, including showing that an action is still in progress.
- **CTL-3** **Choose a descriptive symbol that suggests the behaviour.** The symbol may be all that's shown, so it has to carry the meaning alone.
- **CTL-4** **Use symbol animations to highlight state changes**, and animate the transition between on and off for a toggle.
- **CTL-5** Select a tint colour that works with your brand - the system applies it to a toggle's symbol in its **on** state.
- **CTL-6** Let people configure a control where the action needs more information (which light to switch).
- **CTL-7** **Provide hint text for the Action button** so people understand what press-and-hold does.
- **CTL-8** **Include a placeholder** if your title or value can vary.
- **CTL-9** **Hide sensitive information when the device is locked** - have the system redact the title and value.
- **CTL-10** **Require authentication for actions that affect security** - unlocking a door, starting a car.
- **CTL-11** For a camera experience on a locked device, **use the same camera UI as in your app**, and **tell people how to add the control.**

### 8.4 Live Activities (iOS, iPadOS, macOS menu bar)

Four presentations: **compact**, **minimal**, **expanded** (all three in the Dynamic Island), and **Lock Screen** - plus StandBy and CarPlay variants.

- **LIV-1** **Use Live Activities for tasks and events with a defined beginning and end.** They work best for short-to-medium activities **not exceeding about eight hours.**
- **LIV-2** **Focus on important information people need at a glance.** It doesn't need to show everything.
- **LIV-3** **NEVER use a Live Activity to display ads or promotions.**
- **LIV-4** **NEVER display sensitive information** - a Live Activity is prominently visible, including on the Lock Screen and the Always-On display.
- **LIV-5** Match your app's visual character in both light and dark appearances, so people recognise it.
- **LIV-6** **If you include a logo mark, display it without a container.**
- **LIV-7** **NEVER add elements to your app that draw attention to the Dynamic Island.**
- **LIV-8** **Use large text at medium weight or heavier.**
- **LIV-9** **Adapt to different screen sizes and presentations**, and size the layout to only the space the content needs.
- **LIV-10** **Use consistent margins and concentric placement** - even, matching margins between rounded shapes and the edges, corners included.
- **LIV-11** **NEVER draw content all the way to the edge of the Dynamic Island.** To separate a block of content, put it in an inset container shape or use a thick line.
- **LIV-12** **Dynamically change the height** on the Lock Screen and in the expanded presentation - shrink it when there's less to show.
- **LIV-13** **You cannot customise the background colour for the compact, minimal and expanded presentations** - the Dynamic Island uses a black opaque background. **Tint the key line colour to match your content** (a key line appears around the Dynamic Island against a dark background).
- **LIV-14** **Use animation to reinforce what you're communicating and to draw attention to updates**, including animating layout changes. **Try to avoid overlapping elements** - animate elements out and back in at a new position rather than letting them collide.
- **LIV-15** **Tapping the Live Activity must open the app at the right location.**
- **LIV-16** **Focus on simple, direct actions.** Buttons and toggles consume space that could show useful information.
- **LIV-17** **Start Live Activities at appropriate times and make it easy to turn them off in your app.** Consider an App Shortcut that starts one.
- **LIV-18** **Update only when new content is available.** If the status hasn't changed, don't change the display.
- **LIV-19** **Alert people only for essential updates** - alerts light the screen and play the notification sound by default.
- **LIV-20** **Prefer one Live Activity with a dynamic layout that rotates through events** over several that people must jump between.
- **LIV-21** **Always end a Live Activity immediately when the task ends**, and consider setting a custom dismissal time.
- **LIV-22** **Start with the iPhone design, then refine for other contexts.**
- **LIV-23 (compact)** Show dynamic, essential, easy-to-understand information. **Design the leading and trailing elements to read as a single piece of information** even though the TrueDepth camera separates them, with consistent colour and typography. **Keep content as narrow as possible and snug against the camera** - no padding between content and camera, and don't obscure key information in the status bar.
- **LIV-24 (minimal)** **Make it recognisable.** Prefer updated information over just a logo, while staying identifiable.
- **LIV-25 (expanded)** **Maintain the relative placement of elements** so the layout stays coherent with the compact or minimal version, and **wrap content tightly around the TrueDepth camera** to use space efficiently and diminish the camera's presence.
- **LIV-26 (Lock Screen)** **NEVER replicate notification layouts.** Choose colours that work on a personalised Lock Screen. Check the design, assets and colours in Dark Mode and on an Always-On display. **Verify the system-generated dismiss button colour.** **The standard Lock Screen layout margin is 14 pt**, which aligns the design with notifications.
- **LIV-27 (StandBy)** Update the layout for the larger scale. **Consider the default background colour** - it blends with the device bezel and lets the system scale the activity slightly larger. **Use standard margins and never extend graphics to the screen edge**, or content gets cut off as the activity extends and it looks broken. **Verify the design in Night Mode**, where the system applies a red tint.
- **LIV-28 (CarPlay)** Consider a custom layout for larger text or more information. **The system deactivates interactive elements in CarPlay**, so weigh buttons and toggles accordingly.

**Live Activity dimensions (iOS, pt)**

| Screen | Compact leading | Compact trailing | Minimal | Expanded | Lock Screen |
|---|---|---|---|---|---|
| 430×932 | 62.33×36.67 | 62.33×36.67 | 36.67–45 × 36.67 | 408 × 84–160 | 408 × 84–160 |
| 393×852 | 52.33×36.67 | 52.33×36.67 | 36.67–45 × 36.67 | 371 × 84–160 | 371 × 84–160 |

Dynamic Island width: **250 pt** on Max, Plus and Air models; **230 pt** on the base and Pro models. Expanded width: **408 pt** and **371 pt** respectively. CarPlay Live Activity sizes: 240×78, 240×100, 170×78 pt.

### 8.5 Managing accounts

- **ACC-1** **Explain the benefits of creating an account and how to sign up**, briefly and in a friendly tone.
- **ACC-2** **Delay sign-in for as long as possible.** People abandon apps that force sign-in before anything useful happens.
- **ACC-3** If you don't use Sign in with Apple, **prefer a passkey** - no password to create or enter.
- **ACC-4** **Always name the authentication method.** "Sign In with Face ID", not "Sign In".
- **ACC-5** **Refer only to authentication methods available in the current context.** Don't mention Face ID on a device without it.
- **ACC-6** **In general, don't offer an app-specific setting for opting in to biometric authentication** - people turn it on at system level, so an in-app setting is redundant and confusing.
- **ACC-7** **NEVER use the word "passcode" for account authentication.** A passcode unlocks a device or authenticates for Apple services.
- **ACC-8** **Provide a clear way to initiate account deletion inside the app.** If deletion can't happen in the app, **you must provide a direct link to the webpage where it can.**
- **ACC-9** **Keep the deletion experience consistent** between app and website - neither version longer or more complicated than the other.
- **ACC-10** Consider letting people **schedule deletion for the future**, so they can use remaining services or wait out a subscription period.
- **ACC-11** **Tell people when deletion will complete and notify them when it's finished.**
- **ACC-12** With in-app purchases, **explain how billing and cancellation work on deletion**: an auto-renewable subscription continues to bill through Apple until cancelled, regardless of account deletion, so people need to cancel or request a refund separately. **You must support account deletion even if the subscription wasn't purchased through your app.**
- **ACC-13** If a legal requirement compels you to keep accounts or information, or to follow a specific deletion process, **describe the situation clearly** so people understand what is kept and what the process is.

### 8.6 Ratings and reviews

- **RAT-1** **Ask for a rating only after people have demonstrated engagement** - completing a task or a level.
- **RAT-2** **NEVER interrupt someone mid-task to ask for feedback.**
- **RAT-3** **Avoid pestering.** Repeated requests are irritating and can worsen people's opinion of the app.
- **RAT-4** **Prefer the system-provided prompt.**
- **RAT-5** Weigh resetting your summary rating on a new release against the disadvantage of showing fewer ratings.

---

## 9. What changed in the iOS 27 / iPadOS 27 / macOS 27 cycle

iOS 27, iPadOS 27 and macOS 27 - codenamed **"Golden Gate"** - were announced at WWDC on **8 June 2026** and released on **14 September 2026**.

### 9.1 Verified in the HIG text itself

These are in the current guidelines as I read them, and several of the pages carry 2026 revision dates (the Layout page was last updated **9 September 2026**, "to reflect current best practices"; the Typography specifications gained emphasized weights on **16 December 2025**).

- **Liquid Glass is documented as two named variants - regular and clear** - with explicit guidance on when to use each, and the **35% dark dimming layer** for clear glass over bright content.
- **The two-layer model is stated as a rule**, not a suggestion: Liquid Glass belongs to the functional layer and **must not** appear in the content layer. Sliders and toggles are the only stated exception, taking on the material transiently while being manipulated.
- **Scroll edge effects** replace solid or semi-opaque backgrounds beneath controls, with an `automatic` / hard / soft style choice, one effect per view, and matched heights across split-view panes.
- **The background extension effect** (flip and blur a background image, mirrored beneath sidebars and inspectors) is documented in Layout.
- **App icons are layered**, built in **Icon Composer**, and take on Liquid Glass specular highlights, refraction and translucency, which the system applies dynamically. The icon appearance set is now **default, dark, clear light, clear dark, tinted light, tinted dark** - six variants, and alternate icons need their own.
- **Toolbars**: the `.prominent` style for key actions like Done or Submit; explicit guidance to **reduce toolbar backgrounds and tinted controls**; standard components carry corner radii **concentric with the bar**; the system supplies the overflow menu on iPadOS and macOS.
- **Tab bars on iOS float above content at the bottom on Liquid Glass**, can **minimise** with an attached accessory moving inline on scroll, and can carry a **dedicated search tab** at the trailing end.
- **iPadOS windowing**: apps run full screen or in freely resizable windows with system window controls for tiling, full screen, minimise and close - behaving much like macOS. Window controls sit at the leading edge of the toolbar when windowed.
- **Search on iOS has three documented homes** - a tab in the tab bar (standard or button appearance), a toolbar at bottom or top, or inline with content - with a stated preference for the **bottom** when there's room.
- **Colour**: "even if your app ships in a single appearance mode, provide both light and dark colours to support Liquid Glass adaptivity."
- **Branding**: the recommended way to express brand colour is now to **move it into the content layer**, where it scrolls beneath the glass and gets picked up dynamically, rather than tinting controls.
- **SF Symbols 7+**: **gradient rendering** from a single source colour across all rendering modes, **Draw On / Draw Off** animations, and **Magic Replace** as the default replace animation.
- **Accessibility Nutrition Labels** are the App Store mechanism for declaring accessibility support.
- **Assistive Access** optimisation guidance for iOS and iPadOS: core functionality only, one interaction per screen, and **double confirmation** for anything hard to recover from.

### 9.2 Reported by Apple's release notes and press coverage, not stated in the HIG **[27-press]**

Treat these as well-attested but second-hand. I could not find them written into the HIG pages, and Apple publishes no numeric values for any of them.

- Liquid Glass was **refined rather than replaced**: **darkened edges**, **brighter specular highlights**, and **better diffusion of background content**. Apps pick the refinements up **automatically, without recompiling.**
- A new **Settings → Appearance → Liquid Glass** control: a continuous slider from "ultra clear to fully tinted", labelled **More Clear / Default / More Tinted**, defaulting to the midpoint. This is a systemwide user preference your design has to survive at both extremes.
- **Uniform toolbars** and **edge-to-edge sidebars**.
- **Coloured sidebar icons returned** (Tahoe had largely removed them).
- **macOS window corner radii are now consistent across the system, and reduced** compared with macOS 26 Tahoe.
- **Most of Tahoe's menu-item icons were removed.**
- **Show Borders** arrived in macOS accessibility settings - a system-level way to make control boundaries explicit, which is worth testing against.
- **Icon Composer 2** and **SF Symbols 8**, the latter with over 7,000 symbols.
- The **gyroscopic shimmer** on app icons was removed; icons are now multi-layer with **per-layer refraction**.

### 9.3 What this means in practice

Three consequences worth planning around:

1. **You no longer control the material's appearance - the person does.** With a systemwide clear-to-tinted slider plus Reduce Transparency and Increase Contrast, any given control can render from nearly invisible glass to nearly solid fill. Every rule about contrast, legibility and light/dark colour pairs exists because of this. Test at both ends of the slider and with both accessibility settings on.
2. **The content layer is where brand lives now.** The guidance moved from "tint your controls with your brand colour" to "put your colour in the content and let the glass pick it up". Colouring multiple controls is explicitly called out as wrong.
3. **Concentricity is a real constraint.** Standard components get corner radii concentric with their containing bar, and the app icon's masking matches the curvature of other rounded elements and of the device bezel. Custom controls that use an arbitrary radius look wrong next to system ones, and Apple gives you no number to copy - you get it by using standard components.

---

## 10. The numbers, in one place

Everything Apple publishes as a figure for iOS, iPadOS and macOS.

### Type sizes

| | iOS, iPadOS | macOS |
|---|---|---|
| Default body size | **17 pt** | **13 pt** |
| Minimum size (system or custom fonts) | **11 pt** | **10 pt** |
| Dynamic Type supported | Yes | **No** |
| Standard Dynamic Type steps | xSmall → xxxLarge (7 steps) | n/a |
| Larger accessibility steps | AX1 → AX5 | n/a |
| Body size range across all steps | 14 pt → 53 pt | fixed at 13 pt |
| Text enlargement people should get | **at least 200%** | at least 200% |

### Control sizes and spacing

| | iOS, iPadOS | macOS |
|---|---|---|
| Default control size | **44 × 44 pt** | **28 × 28 pt** |
| Minimum control size | **28 × 28 pt** | **20 × 20 pt** |
| Padding around a bezelled element | ~**12 pt** | ~12 pt |
| Padding around a non-bezelled element's visible edges | ~**24 pt** | ~24 pt |

### Contrast

| Text | Minimum ratio |
|---|---|
| Up to 17 pt, any weight | **4.5:1** |
| 18 pt, any weight | **3:1** |
| Any size, bold | **3:1** |
| Dark Mode floor (any colours) | **4.5:1** |
| Dark Mode target for custom colours, especially small text | **7:1** |

### Materials

| | Value |
|---|---|
| Dark dimming layer behind **clear** Liquid Glass over bright content | **35% opacity** |
| Standard content-layer materials (iOS, iPadOS) | ultra-thin, thin, regular (default), thick |
| Label vibrancy levels (iOS, iPadOS) | label, secondary, tertiary, quaternary |
| Fill vibrancy levels | fill, secondary, tertiary |
| Separator vibrancy levels | one |
| Liquid Glass opacity, blur radius, corner radii | **Apple publishes no numbers** |

### Images and icons

| | Value |
|---|---|
| Scale factors - iOS | @2x and @3x |
| Scale factors - iPadOS | @2x |
| Scale factors - macOS | @1x and @2x |
| App icon layout size (iOS, iPadOS, macOS) | **1024 × 1024 px**, square, layered |
| App icon colour spaces | sRGB, Gray Gamma 2.2, Display P3 |
| macOS document icon smallest size | **16 × 16 px** |
| macOS document icon centre image | **half** the canvas size |
| macOS document icon margin | **~10%** of the canvas; image occupies **~80%** |
| Wide colour | Display P3, 16 bits per channel, PNG |
| SF Symbols weights / scales | 9 weights (ultralight → black); 3 scales (small, medium default, large) |

### Assorted published figures

| | Value |
|---|---|
| Window title length (toolbar) | keep under **15 characters** |
| macOS About-window short app name | **16 characters or fewer** |
| macOS tooltip length | **60–75 characters** |
| macOS split-view thin divider | **1 pt** wide |
| macOS image button padding | **~10 px** |
| macOS radio buttons per group | typically **2 to 5** |
| macOS tab view maximum tabs | **6** |
| Drag threshold before showing a drag image | **~3 pt** |
| RTL font size increase next to all-caps Latin | **+2 pt** |
| Alert buttons | up to **3** |
| Sidebar hierarchy depth | **2 levels** maximum |
| Submenu depth | **1 level** |
| Pull-down button minimum items | **3** |
| Game frame rate | **30–60 fps** |

---

## 11. Review checklist

Run a screen against this. Each item maps to a numbered rule above.

**Structure**
- [ ] Controls and navigation sit in the Liquid Glass functional layer; nothing in the content layer uses Liquid Glass (MAT-1…3)
- [ ] No solid or semi-opaque background beneath controls - a scroll edge effect does the separation instead (LAY-7, SCR-7…10)
- [ ] Full-screen background content extends under sidebars, toolbars and tab bars (LAY-8)
- [ ] Safe areas respected; nothing hidden behind the Dynamic Island or the Mac camera housing (LAY-23, LAY-25)
- [ ] Nothing critical at the bottom of a macOS window or sidebar (LAY-24, SDB-13, WIN-12)
- [ ] Most important content top and leading; related items grouped; hierarchy shown by alignment and indentation (LAY-1…4)

**Adaptivity**
- [ ] Layout driven by size class, not device or orientation; every combination checked (LAY-16…21)
- [ ] Functionality identical across size classes - only visibility changes (LAY-20)
- [ ] Tested at the largest accessibility type size: no truncation, hierarchy intact, columns reduced, layout stacked where needed (TYP-20…24)
- [ ] Tested in light, dark, Increase Contrast, Reduce Transparency, and both ends of the Liquid Glass appearance slider (COL-2…4, DRK-3…4, MAT-10)
- [ ] Orientation-locked screens still resize correctly (LAY-12)

**Type**
- [ ] Body at 17 pt (iOS/iPadOS) or 13 pt (macOS); nothing below 11 pt / 10 pt (TYP-1)
- [ ] No Ultralight, Thin or Light weights (TYP-4)
- [ ] Built-in text styles used; minimum number of typefaces (TYP-6, TYP-12)
- [ ] No tight leading on three or more lines (TYP-14)

**Colour and contrast**
- [ ] Contrast at least 4.5:1 for text up to 17 pt, 3:1 for 18 pt or bold; 7:1 target for small text in dark mode (A11Y-5, DRK-8)
- [ ] No hard-coded system colour values; semantic colours used for their documented purpose (COL-12…14)
- [ ] Colour never the only carrier of meaning (COL-9, A11Y-8, CHT-17)
- [ ] Accent colour used only for primary actions and status, on backgrounds rather than symbols, on one control at a time (MAT-15…17, BRA-2)

**Controls**
- [ ] Every target at least 44 × 44 pt (iOS/iPadOS) or 28 × 28 pt (macOS), with 12/24 pt of padding (A11Y-14…15)
- [ ] Custom buttons have a press state (BTN-2)
- [ ] Primary role never on a destructive action (BTN-9)
- [ ] Standard SF Symbols for standard actions (ICO-1…4, the standard-icons table)
- [ ] Every custom icon and symbol has an accessibility description (ICO-10, SF-29)

**Interaction**
- [ ] Every gesture has a non-gesture alternative (A11Y-17, GST-1, GST-5)
- [ ] Full Keyboard Access works; no system shortcut overridden (A11Y-21…22, KBD-1…3)
- [ ] Nothing auto-dismisses on a timer where an explicit action would do (A11Y-25)
- [ ] Undo available, multiple times, with the result visible (UND-1…3, PRI-2.3)
- [ ] Reduce Motion honoured - springs tightened, z-axis and blur animations replaced with fades (MOT-10)
- [ ] No autoplaying audio or video without controls (A11Y-27)

**Content and copy**
- [ ] Verbs on buttons and links; no "Click here"; no "we"; no "oops" (WRI-6, WRI-7, WRI-12, WRI-17)
- [ ] One capitalisation style per element type, applied consistently (WRI-9)
- [ ] Errors next to the field, blame-free, saying what to do (WRI-16, WRI-23)
- [ ] Empty states guide people to an action and hold nothing crucial (WRI-15)
- [ ] Field hints show the expected format (WRI-22, ENT-2)
- [ ] Gender-neutral, jargon-free, colloquialism-free, humour checked (INC-3…9)

**Modality and interruption**
- [ ] Alerts are critical and actionable; none at launch; none for expected, undoable data loss (ALR-1…4, FDB-5)
- [ ] One modal at a time, dismissible, with confirmation when closing would lose work (MOD-5, MOD-6, MOD-8)
- [ ] Cancel is titled exactly "Cancel"; "OK" only on purely informational alerts (ALR-12, ALR-15)

**Privacy and trust**
- [ ] Permission requested only when the feature needs it, never at launch unless essential (PRV-6, PRV-7)
- [ ] Purpose strings active, specific, sentence case, ending in a period (PRV-8)
- [ ] Any pre-permission screen has exactly one button, not titled "Allow", with no escape route (PRV-9)
- [ ] Nothing that imitates or annotates the system alert (PRV-10)
- [ ] Passwords never prepopulated; secrets in the keychain; no custom auth scheme (ENT-4, PRV-13, PRV-14)

**Brand**
- [ ] Brand colour in the content layer, not spread across controls (BRA-3)
- [ ] No logo repeated through the app; no branding on the launch screen (BRA-8, BRA-9, LNC-7)
- [ ] Launch screen matches the first screen and carries no text (LNC-5, LNC-6)
- [ ] Standard components in standard places, whatever the visual style (BRA-5, BRA-7)

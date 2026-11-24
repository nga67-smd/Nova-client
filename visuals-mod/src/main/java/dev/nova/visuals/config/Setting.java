package dev.nova.visuals.config;

import com.google.gson.JsonElement;
import com.google.gson.JsonPrimitive;
import dev.nova.visuals.core.Colors;
import dev.nova.visuals.core.Easing;

/** One adjustable value of a module. Subclasses know how to save and load themselves. */
public abstract class Setting {
    public final String id, name;
    /** Optional: only shown in the menu while this returns true. */
    public java.util.function.BooleanSupplier visible = () -> true;

    protected Setting(String id, String name) { this.id = id; this.name = name; }

    public abstract JsonElement save();
    public abstract void load(JsonElement e);

    public Setting showIf(java.util.function.BooleanSupplier v) { this.visible = v; return this; }

    public static final class Bool extends Setting {
        public boolean value;
        public Bool(String id, String name, boolean def) { super(id, name); value = def; }
        @Override public JsonElement save() { return new JsonPrimitive(value); }
        @Override public void load(JsonElement e) { if (e.isJsonPrimitive() && e.getAsJsonPrimitive().isBoolean()) value = e.getAsBoolean(); }
    }

    public static final class Num extends Setting {
        public float value;
        public final float min, max, step;
        public final String suffix;
        public Num(String id, String name, float def, float min, float max, float step, String suffix) {
            super(id, name); this.value = def; this.min = min; this.max = max; this.step = step; this.suffix = suffix;
        }
        public void set(float v) {
            v = Easing.clamp(v, min, max);
            if (step > 0) v = Math.round(v / step) * step;
            value = v;
        }
        public int asInt() { return Math.round(value); }
        @Override public JsonElement save() { return new JsonPrimitive(value); }
        @Override public void load(JsonElement e) { if (e.isJsonPrimitive() && e.getAsJsonPrimitive().isNumber()) set(e.getAsFloat()); }
    }

    public static final class Color extends Setting {
        public int value;
        public Color(String id, String name, int def) { super(id, name); value = def & 0xFFFFFF; }
        @Override public JsonElement save() { return new JsonPrimitive(Colors.hex(value)); }
        @Override public void load(JsonElement e) {
            if (e.isJsonPrimitive() && e.getAsJsonPrimitive().isString()) {
                int c = Colors.parseHex(e.getAsString());
                if (c >= 0) value = c;
            }
        }
    }

    public static final class Choice extends Setting {
        public int index;
        public final String[] options;
        public Choice(String id, String name, int def, String... options) { super(id, name); this.options = options; this.index = def; }
        public String get() { return options[index]; }
        public void next() { index = (index + 1) % options.length; }
        @Override public JsonElement save() { return new JsonPrimitive(options[index]); }
        @Override public void load(JsonElement e) {
            if (!e.isJsonPrimitive()) return;
            String s = e.getAsString();
            for (int i = 0; i < options.length; i++) if (options[i].equalsIgnoreCase(s)) index = i;
        }
    }
}

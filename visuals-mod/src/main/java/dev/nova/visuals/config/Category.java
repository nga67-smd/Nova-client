package dev.nova.visuals.config;

public enum Category {
    VISUALS("Visuals"), PARTICLES("Particles"), ENVIRONMENT("Environment"), ANIMATIONS("Animations"),
    COSMETICS("Cosmetics"), HUD("HUD"), SETTINGS("Settings");

    public final String label;
    Category(String label) { this.label = label; }
}

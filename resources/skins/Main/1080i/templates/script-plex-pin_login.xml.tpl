{% extends "base.xml.tpl" %}
{% block controls %}
<control type="image">
    <posx>0</posx>
    <posy>0</posy>
    <width>1920</width>
    <height>1080</height>
    <texture background="true">script.plex/home/background-fallback_black.png</texture>
</control>
<control type="label">
    <posx>210</posx>
    <posy>{{ vscale(260) }}</posy>
    <width>1500</width>
    <height>{{ vscale(90) }}</height>
    <font>font45_title</font>
    <align>left</align>
    <aligny>center</aligny>
    <textcolor>FFFFFFFF</textcolor>
    <label>$INFO[Window.Property(heading)]</label>
</control>
<control type="label">
    <posx>210</posx>
    <posy>{{ vscale(380) }}</posy>
    <width>1500</width>
    <height>{{ vscale(140) }}</height>
    <font>font14</font>
    <align>left</align>
    <aligny>top</aligny>
    <wrapmultiline>true</wrapmultiline>
    <textcolor>FFFFFFFF</textcolor>
    <label>$INFO[Window.Property(instructions)]</label>
</control>

<control type="label">
    <posx>270</posx>
    <posy>{{ vscale(738) }}</posy>
    <width>800</width>
    <height>{{ vscale(153) }}</height>
    <font>WeatherTemp</font>
    <align>left</align>
    <aligny>center</aligny>
    <textcolor>FFFFFFFF</textcolor>
    <label>$INFO[Window.Property(pin)]</label>
</control>

<control type="grouplist" id="400">
    <defaultcontrol>406</defaultcontrol>
    <posx>265</posx>
    <posy>{{ vscale(708) }}</posy>
    <width>1000</width>

    <height>{{ vscale(200) }}</height>
    <align>left</align>
    <itemgap>0</itemgap>
    <orientation>horizontal</orientation>
    <control type="image">
        <width>200</width>
        <height>{{ vscale(200) }}</height>
        <texture>$INFO[Window.Property(pin.image.0)]</texture>
    </control>
    <control type="image">
        <width>200</width>
        <height>{{ vscale(200) }}</height>
        <texture>$INFO[Window.Property(pin.image.1)]</texture>
    </control>
    <control type="image">
        <width>200</width>
        <height>{{ vscale(200) }}</height>
        <texture>$INFO[Window.Property(pin.image.2)]</texture>
    </control>
    <control type="image">
        <width>200</width>
        <height>{{ vscale(200) }}</height>
        <texture>$INFO[Window.Property(pin.image.3)]</texture>
    </control>

</control>
{% endblock controls %}
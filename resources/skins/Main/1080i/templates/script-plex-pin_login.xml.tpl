{% extends "base.xml.tpl" %}
{% block headers %}<defaultcontrol always="true">201</defaultcontrol>{% endblock %}
{% block controls %}
<control type="image">
    <posx>0</posx>
    <posy>0</posy>
    <width>1920</width>
    <height>1080</height>
    <texture colordiffuse="FF141417">script.plex/white-square.png</texture>
</control>
<control type="group">
    <posx>580</posx>
    <posy>{{ vscale(60) }}</posy>
    <control type="image">
        <width>760</width>
        <height>{{ vscale(960) }}</height>
        <texture colordiffuse="FF1E1E23" border="10">script.plex/white-square-rounded.png</texture>
    </control>
    <control type="image">
        <width>760</width>
        <height>{{ vscale(960) }}</height>
        <texture colordiffuse="14FFFFFF" border="10">script.plex/white-outline-rounded.png</texture>
    </control>
    <control type="label">
        <posx>56</posx>
        <posy>{{ vscale(44) }}</posy>
        <width>648</width>
        <height>{{ vscale(76) }}</height>
        <font>font45_title</font>
        <textcolor>FFFFFFFF</textcolor>
        <label>$INFO[Window.Property(server.name)]</label>
    </control>
    <control type="label">
        <posx>56</posx>
        <posy>{{ vscale(124) }}</posy>
        <width>648</width>
        <height>{{ vscale(40) }}</height>
        <font>font12</font>
        <textcolor>FF9A9AA3</textcolor>
        <label>$INFO[Window.Property(subtitle)]</label>
    </control>
    <control type="group">
        <visible>!String.IsEmpty(Window.Property(password.enabled))</visible>
        <control type="label">
            <posx>56</posx>
            <posy>{{ vscale(186) }}</posy>
            <width>648</width>
            <height>{{ vscale(36) }}</height>
            <font>font10</font>
            <textcolor>FFD4D4D8</textcolor>
            <label>$INFO[Window.Property(label.username)]</label>
        </control>
        <control type="button" id="201">
            <posx>56</posx>
            <posy>{{ vscale(224) }}</posy>
            <width>648</width>
            <height>{{ vscale(68) }}</height>
            <font>font12</font>
            <aligny>center</aligny>
            <textoffsetx>22</textoffsetx>
            <textcolor>FFFFFFFF</textcolor>
            <focusedcolor>FFFFFFFF</focusedcolor>
            <texturefocus colordiffuse="FFFFFFFF" border="10">script.plex/white-outline-rounded.png</texturefocus>
            <texturenofocus colordiffuse="33FFFFFF" border="10">script.plex/white-outline-rounded.png</texturenofocus>
            <ondown>202</ondown>
            <label>$INFO[Window.Property(username)]</label>
        </control>
        <control type="label">
            <posx>56</posx>
            <posy>{{ vscale(308) }}</posy>
            <width>648</width>
            <height>{{ vscale(36) }}</height>
            <font>font10</font>
            <textcolor>FFD4D4D8</textcolor>
            <label>$INFO[Window.Property(label.password)]</label>
        </control>
        <control type="button" id="202">
            <posx>56</posx>
            <posy>{{ vscale(346) }}</posy>
            <width>648</width>
            <height>{{ vscale(68) }}</height>
            <font>font12</font>
            <aligny>center</aligny>
            <textoffsetx>22</textoffsetx>
            <textcolor>FFFFFFFF</textcolor>
            <focusedcolor>FFFFFFFF</focusedcolor>
            <texturefocus colordiffuse="FFFFFFFF" border="10">script.plex/white-outline-rounded.png</texturefocus>
            <texturenofocus colordiffuse="33FFFFFF" border="10">script.plex/white-outline-rounded.png</texturenofocus>
            <onup>201</onup>
            <ondown>203</ondown>
            <label>$INFO[Window.Property(password)]</label>
        </control>
        <control type="label">
            <posx>56</posx>
            <posy>{{ vscale(424) }}</posy>
            <width>648</width>
            <height>{{ vscale(36) }}</height>
            <font>font10</font>
            <textcolor>FFF87171</textcolor>
            <label>$INFO[Window.Property(error)]</label>
        </control>
        <control type="button" id="203">
            <posx>56</posx>
            <posy>{{ vscale(468) }}</posy>
            <width>648</width>
            <height>{{ vscale(68) }}</height>
            <font>font12</font>
            <align>center</align>
            <aligny>center</aligny>
            <textcolor>FF18181B</textcolor>
            <focusedcolor>FF000000</focusedcolor>
            <texturefocus colordiffuse="FFFFFFFF" border="10">script.plex/white-square-rounded.png</texturefocus>
            <texturenofocus colordiffuse="FFB4B4BB" border="10">script.plex/white-square-rounded.png</texturenofocus>
            <onup>202</onup>
            <ondown>204</ondown>
            <label>$INFO[Window.Property(label.signin)]</label>
        </control>
        <control type="image">
            <posx>56</posx>
            <posy>{{ vscale(566) }}</posy>
            <width>648</width>
            <height>1</height>
            <texture colordiffuse="1FFFFFFF">script.plex/white-square-1px.png</texture>
        </control>
    </control>
    <control type="label">
        <posx>56</posx>
        <posy>{{ vscale(588) }}</posy>
        <width>648</width>
        <height>{{ vscale(40) }}</height>
        <font>font13</font>
        <textcolor>FFFFFFFF</textcolor>
        <label>$INFO[Window.Property(label.phone)]</label>
    </control>
    <control type="image">
        <posx>56</posx>
        <posy>{{ vscale(640) }}</posy>
        <width>240</width>
        <height>{{ vscale(240) }}</height>
        <aspectratio>keep</aspectratio>
        <texture background="true">$INFO[Window.Property(qr)]</texture>
    </control>
    <control type="label">
        <posx>328</posx>
        <posy>{{ vscale(640) }}</posy>
        <width>376</width>
        <height>{{ vscale(150) }}</height>
        <font>font10</font>
        <aligny>top</aligny>
        <wrapmultiline>true</wrapmultiline>
        <textcolor>FFA1A1AA</textcolor>
        <label>$INFO[Window.Property(instructions)]</label>
    </control>
    <control type="label">
        <posx>328</posx>
        <posy>{{ vscale(800) }}</posy>
        <width>376</width>
        <height>{{ vscale(80) }}</height>
        <font>font32_title</font>
        <textcolor>FFFFFFFF</textcolor>
        <label>$INFO[Window.Property(pin)]</label>
    </control>
    <control type="image">
        <posx>56</posx>
        <posy>{{ vscale(896) }}</posy>
        <width>648</width>
        <height>1</height>
        <texture colordiffuse="1FFFFFFF">script.plex/white-square-1px.png</texture>
    </control>
    <control type="label">
        <posx>56</posx>
        <posy>{{ vscale(906) }}</posy>
        <width>470</width>
        <height>{{ vscale(46) }}</height>
        <font>font10</font>
        <aligny>center</aligny>
        <textcolor>FFA1A1AA</textcolor>
        <label>$INFO[Window.Property(label.server)]  [COLOR FFFFFFFF]$INFO[Window.Property(address)][/COLOR]</label>
    </control>
    <control type="button" id="204">
        <posx>544</posx>
        <posy>{{ vscale(906) }}</posy>
        <width>160</width>
        <height>{{ vscale(46) }}</height>
        <font>font10</font>
        <align>center</align>
        <aligny>center</aligny>
        <textcolor>FFD4D4D8</textcolor>
        <focusedcolor>FFFFFFFF</focusedcolor>
        <texturefocus colordiffuse="FFFFFFFF" border="10">script.plex/white-outline-rounded.png</texturefocus>
        <texturenofocus colordiffuse="33FFFFFF" border="10">script.plex/white-outline-rounded.png</texturenofocus>
        <onup>203</onup>
        <label>$INFO[Window.Property(label.change)]</label>
    </control>
</control>
{% endblock controls %}

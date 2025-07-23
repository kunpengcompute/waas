%define projectdir /usr/local/waasbooster

Name: waasbooster
Version: 1.0.0
Release: 1%{?dist}
Summary: load aware
License: FIXME
BuildArch: %{_build_arch}
Vendor: Huawei

Provides: waasbooster = 1.0.0

%description
WAAS Booster是一款在线容器quota调优工具

%prep
unzip %{_sourcedir}/waasbooster.zip

%build


%install
mkdir -p %{buildroot}/usr/lib/systemd/system/
mkdir -p %{buildroot}/usr/bin/
mkdir -p %{buildroot}/%{projectdir}
cp %{_builddir}/src/waasbooster/* %{buildroot}/%{projectdir}

install -m 444 src/waasbooster/waasbooster.service %{buildroot}/usr/lib/systemd/system/waasbooster.service

%files
%dir %attr(644, waas, waas) %{projectdir}
%defattr (0440, waas, waas)
%{projectdir}/*
%dir %attr(644, waas, waas) %{projectdir}
%attr(644, root, root) /usr/lib/systemd/system/waasbooster.service

%pre -p /bin/sh
getent group waas &> /dev/null || \
groupadd -r waas &> /dev/null
getent passwd waas &> /dev/null || \
useradd -r -g waas -d /usr/local/waasbooster -s /sbin/nologin \
-c 'Waas booster' waas &> /dev/null
if [ $SUDO_USER ]; then
    usermod -a -G waas $SUDO_USER
elif [ $USER ]; then
    usermod -a -G waas $USER
else
    usermod -a -G waas `whoami`
fi
exit 0

%post -p /bin/sh
mkdir -p /var/waasbooster
chown waas:waas /var/waasbooster
chmod 750 /var/waasbooster
mkdir -p /var/run/waasbooster_manager
systemctl enable waasbooster.service
exit 0

%preun -p /bin/sh
exit 0

%postun -p /bin/sh
rm -rf /usr/local/waasbooster
rm -rf /var/waasbooster
rm -rf /var/run/waasbooster_manager
exit 0
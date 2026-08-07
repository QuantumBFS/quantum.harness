use anyhow::{Context, Result, bail, ensure};
use std::ffi::{CStr, CString};
use std::fs::File;
use std::io::{self, Read};
use std::os::fd::{AsRawFd, FromRawFd, RawFd};
use std::path::{Component, Path, PathBuf};

const RESOLVE_NO_MAGICLINKS: u64 = 0x02;
const RESOLVE_NO_SYMLINKS: u64 = 0x04;
const RESOLVE_BENEATH: u64 = 0x08;
const RENAME_NOREPLACE: libc::c_uint = 1;

#[repr(C)]
struct OpenHow {
    flags: u64,
    mode: u64,
    resolve: u64,
}

fn component_cstring(name: &str) -> io::Result<CString> {
    if name.is_empty() || name == "." || name == ".." || name.contains('/') {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "invalid descriptor-relative path component",
        ));
    }
    CString::new(name)
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "path component contains NUL"))
}

fn name_cstring(name: &str) -> Result<CString> {
    component_cstring(name).context("invalid descriptor-relative path component")
}

fn openat2(parent: RawFd, name: &CStr, flags: i32, mode: u32) -> io::Result<File> {
    let how = OpenHow {
        flags: (flags | libc::O_CLOEXEC | libc::O_NOFOLLOW) as u64,
        mode: mode as u64,
        resolve: RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS | RESOLVE_NO_MAGICLINKS,
    };
    // SAFETY: `name` and `how` are valid for the duration of the syscall, and
    // a successful return transfers ownership of a newly opened descriptor.
    let descriptor = unsafe {
        libc::syscall(
            libc::SYS_openat2,
            parent,
            name.as_ptr(),
            &how,
            std::mem::size_of::<OpenHow>(),
        )
    };
    if descriptor < 0 {
        Err(io::Error::last_os_error())
    } else {
        // SAFETY: openat2 returned a new owned descriptor.
        Ok(unsafe { File::from_raw_fd(descriptor as RawFd) })
    }
}

fn openat_fallback(parent: RawFd, name: &CStr, flags: i32, mode: u32) -> io::Result<File> {
    // Each caller supplies exactly one validated component. O_NOFOLLOW therefore
    // provides the same no-symlink/beneath-parent property as openat2 for this
    // descriptor-anchored traversal; there are no intermediate components,
    // slashes, or ".." for the legacy kernel to resolve.
    let descriptor = unsafe {
        libc::syscall(
            libc::SYS_openat,
            parent,
            name.as_ptr(),
            flags | libc::O_CLOEXEC | libc::O_NOFOLLOW,
            mode,
        )
    };
    if descriptor < 0 {
        Err(io::Error::last_os_error())
    } else {
        // SAFETY: openat returned a new owned descriptor.
        Ok(unsafe { File::from_raw_fd(descriptor as RawFd) })
    }
}

fn secure_openat_with<F>(
    parent: RawFd,
    name: &str,
    flags: i32,
    mode: u32,
    openat2_attempt: F,
) -> io::Result<File>
where
    F: FnOnce(RawFd, &CStr, i32, u32) -> io::Result<File>,
{
    let name = component_cstring(name)?;
    match openat2_attempt(parent, &name, flags, mode) {
        Err(error) if error.raw_os_error() == Some(libc::ENOSYS) => {
            openat_fallback(parent, &name, flags, mode)
        }
        result => result,
    }
}

fn secure_openat(parent: RawFd, name: &str, flags: i32, mode: u32) -> io::Result<File> {
    secure_openat_with(parent, name, flags, mode, openat2)
}

fn fstat(file: &File) -> io::Result<libc::stat> {
    // SAFETY: zero is a valid initial representation for `stat`, and fstat
    // initializes it before it is read.
    let mut value: libc::stat = unsafe { std::mem::zeroed() };
    // SAFETY: the descriptor and output pointer are valid.
    if unsafe { libc::fstat(file.as_raw_fd(), &mut value) } != 0 {
        Err(io::Error::last_os_error())
    } else {
        Ok(value)
    }
}

fn ensure_kind(file: &File, expected: libc::mode_t, label: &str) -> Result<()> {
    let status = fstat(file).with_context(|| format!("cannot fstat {label}"))?;
    ensure!(
        status.st_mode & libc::S_IFMT == expected,
        "{label} has an unexpected descriptor type"
    );
    Ok(())
}

#[derive(Debug)]
pub struct Dir {
    file: File,
}

impl Dir {
    pub fn from_inherited_fd(descriptor: RawFd) -> Result<Self> {
        ensure!(
            descriptor >= 0,
            "output directory descriptor must be nonnegative"
        );
        // SAFETY: fcntl duplicates an open descriptor without resolving any
        // pathname. The returned descriptor is independently owned.
        let duplicate = unsafe { libc::fcntl(descriptor, libc::F_DUPFD_CLOEXEC, 0) };
        if duplicate < 0 {
            return Err(io::Error::last_os_error())
                .context("cannot duplicate inherited output directory descriptor");
        }
        // SAFETY: F_DUPFD_CLOEXEC returned a new owned descriptor.
        let file = unsafe { File::from_raw_fd(duplicate) };
        ensure_kind(&file, libc::S_IFDIR, "inherited output directory")?;
        Ok(Self { file })
    }

    fn root() -> Result<Self> {
        let file = File::open("/").context("cannot open filesystem root")?;
        ensure_kind(&file, libc::S_IFDIR, "filesystem root")?;
        Ok(Self { file })
    }

    pub fn open_dir(&self, name: &str) -> Result<Self> {
        let file = secure_openat(
            self.file.as_raw_fd(),
            name,
            libc::O_RDONLY | libc::O_DIRECTORY,
            0,
        )
        .with_context(|| format!("cannot securely open directory {name}"))?;
        ensure_kind(&file, libc::S_IFDIR, name)?;
        Ok(Self { file })
    }

    pub fn open_dir_optional(&self, name: &str) -> Result<Option<Self>> {
        match secure_openat(
            self.file.as_raw_fd(),
            name,
            libc::O_RDONLY | libc::O_DIRECTORY,
            0,
        ) {
            Ok(file) => {
                ensure_kind(&file, libc::S_IFDIR, name)?;
                Ok(Some(Self { file }))
            }
            Err(error) if error.raw_os_error() == Some(libc::ENOENT) => Ok(None),
            Err(error) => Err(error)
                .with_context(|| format!("cannot securely inspect optional directory {name}")),
        }
    }

    pub fn open_or_create_dir(&self, name: &str) -> Result<Self> {
        match self.open_dir(name) {
            Ok(directory) => Ok(directory),
            Err(error)
                if error
                    .root_cause()
                    .downcast_ref::<io::Error>()
                    .and_then(io::Error::raw_os_error)
                    == Some(libc::ENOENT) =>
            {
                let name_c = name_cstring(name)?;
                // SAFETY: parent descriptor and component pointer are valid.
                let result =
                    unsafe { libc::mkdirat(self.file.as_raw_fd(), name_c.as_ptr(), 0o700) };
                if result != 0 {
                    let mkdir_error = io::Error::last_os_error();
                    if mkdir_error.raw_os_error() != Some(libc::EEXIST) {
                        return Err(mkdir_error)
                            .with_context(|| format!("cannot create directory {name}"));
                    }
                }
                let directory = self.open_dir(name)?;
                directory.sync().context("cannot fsync new directory")?;
                self.sync().context("cannot fsync new directory parent")?;
                Ok(directory)
            }
            Err(error) => Err(error),
        }
    }

    pub fn create_dir(&self, name: &str) -> Result<Self> {
        let name_c = name_cstring(name)?;
        // SAFETY: parent descriptor and component pointer are valid.
        if unsafe { libc::mkdirat(self.file.as_raw_fd(), name_c.as_ptr(), 0o700) } != 0 {
            return Err(io::Error::last_os_error())
                .with_context(|| format!("cannot exclusively create directory {name}"));
        }
        self.open_dir(name)
    }

    pub fn open_file(&self, name: &str) -> Result<File> {
        let file = secure_openat(self.file.as_raw_fd(), name, libc::O_RDONLY, 0)
            .with_context(|| format!("cannot securely open file {name}"))?;
        ensure_kind(&file, libc::S_IFREG, name)?;
        Ok(file)
    }

    pub fn open_file_optional(&self, name: &str) -> Result<Option<File>> {
        match secure_openat(self.file.as_raw_fd(), name, libc::O_RDONLY, 0) {
            Ok(file) => {
                ensure_kind(&file, libc::S_IFREG, name)?;
                Ok(Some(file))
            }
            Err(error) if error.raw_os_error() == Some(libc::ENOENT) => Ok(None),
            Err(error) => {
                Err(error).with_context(|| format!("cannot securely inspect optional file {name}"))
            }
        }
    }

    pub fn create_file(&self, name: &str) -> Result<File> {
        let file = secure_openat(
            self.file.as_raw_fd(),
            name,
            libc::O_WRONLY | libc::O_CREAT | libc::O_EXCL,
            0o600,
        )
        .with_context(|| format!("cannot securely create file {name}"))?;
        ensure_kind(&file, libc::S_IFREG, name)?;
        Ok(file)
    }

    pub fn entries(&self) -> Result<Vec<String>> {
        // SAFETY: dup returns a new descriptor on success.
        let duplicate = unsafe { libc::dup(self.file.as_raw_fd()) };
        if duplicate < 0 {
            return Err(io::Error::last_os_error())
                .context("cannot duplicate directory descriptor");
        }
        // SAFETY: the duplicated descriptor refers to a directory and SEEK_SET
        // resets its shared directory offset before each complete scan.
        if unsafe { libc::lseek(duplicate, 0, libc::SEEK_SET) } < 0 {
            // SAFETY: the duplicated descriptor is still owned here.
            unsafe { libc::close(duplicate) };
            return Err(io::Error::last_os_error()).context("cannot rewind directory descriptor");
        }
        // SAFETY: fdopendir takes ownership of the duplicated descriptor.
        let stream = unsafe { libc::fdopendir(duplicate) };
        if stream.is_null() {
            // SAFETY: fdopendir failed and did not take ownership.
            unsafe { libc::close(duplicate) };
            return Err(io::Error::last_os_error()).context("cannot open directory stream");
        }
        let mut names = Vec::new();
        loop {
            // SAFETY: `stream` remains valid until closed below.
            let entry = unsafe { libc::readdir(stream) };
            if entry.is_null() {
                break;
            }
            // SAFETY: d_name is NUL terminated by readdir.
            let bytes = unsafe { CStr::from_ptr((*entry).d_name.as_ptr()) }.to_bytes();
            if bytes == b"." || bytes == b".." {
                continue;
            }
            names.push(
                std::str::from_utf8(bytes)
                    .context("directory entry is not UTF-8")?
                    .to_owned(),
            );
        }
        // SAFETY: closes both the stream and duplicated descriptor.
        if unsafe { libc::closedir(stream) } != 0 {
            return Err(io::Error::last_os_error()).context("cannot close directory stream");
        }
        names.sort();
        Ok(names)
    }

    pub fn rename_noreplace(&self, source: &str, destination: &Dir, target: &str) -> Result<bool> {
        renameat2(self, source, destination, target, RENAME_NOREPLACE)
    }

    pub fn rename_replace(&self, source: &str, destination: &Dir, target: &str) -> Result<()> {
        ensure!(
            renameat2(self, source, destination, target, 0)?,
            "replace rename unexpectedly reported EEXIST"
        );
        Ok(())
    }

    pub fn link_noreplace(&self, source: &str, destination: &Dir, target: &str) -> Result<bool> {
        let source = name_cstring(source)?;
        let target = name_cstring(target)?;
        // SAFETY: both directory descriptors and component pointers are valid.
        // A zero flag set hard-links the directory entry itself and never follows
        // a source symlink.
        let result = unsafe {
            libc::syscall(
                libc::SYS_linkat,
                self.raw_fd() as libc::c_long,
                source.as_ptr(),
                destination.raw_fd() as libc::c_long,
                target.as_ptr(),
                0,
            )
        };
        if result == 0 {
            Ok(true)
        } else {
            let error = io::Error::last_os_error();
            if error.raw_os_error() == Some(libc::EEXIST) {
                Ok(false)
            } else {
                Err(error).context("descriptor-relative hard link failed")
            }
        }
    }

    pub fn sync(&self) -> io::Result<()> {
        self.file.sync_all()
    }

    pub fn identity(&self) -> Result<(u64, u64)> {
        let status = fstat(&self.file).context("cannot fstat directory")?;
        Ok((status.st_dev, status.st_ino))
    }

    pub fn same_entry(&self, name: &str, expected: &Dir) -> Result<bool> {
        Ok(self.open_dir(name)?.identity()? == expected.identity()?)
    }

    pub fn raw_fd(&self) -> RawFd {
        self.file.as_raw_fd()
    }

    pub fn try_clone(&self) -> Result<Self> {
        Ok(Self {
            file: self
                .file
                .try_clone()
                .context("cannot duplicate retained directory descriptor")?,
        })
    }
}

fn renameat2(
    source: &Dir,
    source_name: &str,
    destination: &Dir,
    target_name: &str,
    flags: libc::c_uint,
) -> Result<bool> {
    let source_name = name_cstring(source_name)?;
    let target_name = name_cstring(target_name)?;
    // SAFETY: both directory descriptors and component pointers are valid.
    // Invoke the kernel directly because older glibc versions do not export
    // the renameat2 wrapper even when the running kernel supports the syscall.
    let result = unsafe {
        libc::syscall(
            libc::SYS_renameat2,
            source.raw_fd() as libc::c_long,
            source_name.as_ptr(),
            destination.raw_fd() as libc::c_long,
            target_name.as_ptr(),
            flags as libc::c_ulong,
        )
    };
    if result == 0 {
        Ok(true)
    } else {
        let error = io::Error::last_os_error();
        if flags == RENAME_NOREPLACE && error.raw_os_error() == Some(libc::EEXIST) {
            Ok(false)
        } else if matches!(
            error.raw_os_error(),
            Some(libc::ENOSYS) | Some(libc::EINVAL) | Some(libc::EOPNOTSUPP)
        ) {
            // CentOS 7 kernels and some NFS servers reject renameat2 even
            // though descriptor-relative renameat is available. QMC_SSE's
            // per-run lock serializes publishers, so an explicit destination
            // check preserves no-replace behavior for this compatibility path.
            let target_text = target_name
                .to_str()
                .context("rename target is not valid UTF-8")?;
            if flags == RENAME_NOREPLACE
                && destination
                    .entries()?
                    .iter()
                    .any(|entry| entry == target_text)
            {
                return Ok(false);
            }
            // SAFETY: both retained directory descriptors and component
            // pointers are valid; renameat does not follow either component.
            let fallback = unsafe {
                libc::renameat(
                    source.raw_fd(),
                    source_name.as_ptr(),
                    destination.raw_fd(),
                    target_name.as_ptr(),
                )
            };
            if fallback == 0 {
                Ok(true)
            } else {
                Err(io::Error::last_os_error())
                    .context("descriptor-relative rename fallback failed")
            }
        } else {
            Err(error).context("descriptor-relative rename failed")
        }
    }
}

fn absolute_components(path: &Path) -> Result<(PathBuf, Vec<String>)> {
    let absolute = if path.is_absolute() {
        path.to_path_buf()
    } else {
        std::env::current_dir()
            .context("cannot resolve current directory")?
            .join(path)
    };
    let mut components = Vec::new();
    for component in absolute.components() {
        match component {
            Component::RootDir => {}
            Component::Normal(value) => components.push(
                value
                    .to_str()
                    .context("path component is not UTF-8")?
                    .to_owned(),
            ),
            Component::CurDir => {}
            Component::ParentDir | Component::Prefix(_) => {
                bail!("path must not contain parent or platform-prefix components")
            }
        }
    }
    ensure!(
        !components.is_empty(),
        "path must not resolve to filesystem root"
    );
    Ok((absolute, components))
}

pub fn canonical_requested_path(path: &Path) -> Result<String> {
    let (_, components) = absolute_components(path)?;
    Ok(format!("/{}", components.join("/")))
}

pub fn open_absolute_file(path: &Path) -> Result<File> {
    let (_, mut components) = absolute_components(path)?;
    let name = components.pop().context("file path has no basename")?;
    let mut directory = Dir::root()?;
    for component in components {
        directory = directory.open_dir(&component)?;
    }
    directory.open_file(&name)
}

pub struct AnchoredDir {
    pub directory: Dir,
    links: Vec<AnchorLink>,
}

struct AnchorLink {
    parent: Dir,
    child: Dir,
    name: String,
}

impl AnchoredDir {
    pub fn from_inherited_fd(descriptor: RawFd) -> Result<Self> {
        Ok(Self {
            directory: Dir::from_inherited_fd(descriptor)?,
            links: Vec::new(),
        })
    }

    pub fn verify(&self) -> Result<()> {
        for link in &self.links {
            ensure!(
                link.parent.same_entry(&link.name, &link.child)?,
                "output path ancestor {} was replaced",
                link.name
            );
        }
        Ok(())
    }
}

pub fn open_or_create_anchored_dir(path: &Path) -> Result<AnchoredDir> {
    let (_, components) = absolute_components(path)?;
    let mut parent = Dir::root()?;
    let mut links: Vec<AnchorLink> = Vec::with_capacity(components.len());
    for component in components {
        for link in &links {
            ensure!(
                link.parent.same_entry(&link.name, &link.child)?,
                "output path ancestor {} was replaced during creation",
                link.name
            );
        }
        let child = parent.open_or_create_dir(&component)?;
        links.push(AnchorLink {
            parent: parent.try_clone()?,
            child: child.try_clone()?,
            name: component,
        });
        parent = child;
    }
    Ok(AnchoredDir {
        directory: parent,
        links,
    })
}

pub fn read_regular_file(mut file: File, label: &str) -> Result<Vec<u8>> {
    ensure_kind(&file, libc::S_IFREG, label)?;
    let mut bytes = Vec::new();
    file.read_to_end(&mut bytes)
        .with_context(|| format!("cannot read {label} descriptor"))?;
    Ok(bytes)
}

pub fn duplicate_inherited_file(descriptor: RawFd, label: &str) -> Result<File> {
    ensure!(descriptor >= 0, "{label} descriptor must be nonnegative");
    // SAFETY: fcntl duplicates an open descriptor without resolving a path.
    let duplicate = unsafe { libc::fcntl(descriptor, libc::F_DUPFD_CLOEXEC, 0) };
    if duplicate < 0 {
        return Err(io::Error::last_os_error())
            .with_context(|| format!("cannot duplicate inherited {label} descriptor"));
    }
    // SAFETY: F_DUPFD_CLOEXEC returned a new owned descriptor.
    let file = unsafe { File::from_raw_fd(duplicate) };
    ensure_kind(&file, libc::S_IFREG, label)?;
    Ok(file)
}

pub fn read_regular_file_limited(file: File, label: &str, maximum: u64) -> Result<Vec<u8>> {
    ensure_kind(&file, libc::S_IFREG, label)?;
    let status = fstat(&file).with_context(|| format!("cannot fstat {label}"))?;
    ensure!(
        status.st_size >= 0 && status.st_size as u64 <= maximum,
        "{label} exceeds byte ceiling of {maximum}"
    );
    let mut bytes = Vec::with_capacity(status.st_size as usize);
    file.take(maximum + 1)
        .read_to_end(&mut bytes)
        .with_context(|| format!("cannot read {label} descriptor"))?;
    ensure!(
        bytes.len() as u64 <= maximum,
        "{label} grew beyond byte ceiling while reading"
    );
    Ok(bytes)
}

pub fn file_identity(file: &File) -> Result<(u64, u64)> {
    let status = fstat(file).context("cannot fstat file")?;
    Ok((status.st_dev, status.st_ino))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::os::unix::fs::symlink;
    use std::sync::atomic::{AtomicU64, Ordering};

    static FIXTURE_COUNTER: AtomicU64 = AtomicU64::new(0);

    struct Fixture {
        path: PathBuf,
    }

    impl Fixture {
        fn new() -> Self {
            let path = std::env::temp_dir().join(format!(
                "qmc-sse-secure-fs-{}-{}",
                std::process::id(),
                FIXTURE_COUNTER.fetch_add(1, Ordering::Relaxed)
            ));
            fs::create_dir(&path).expect("create secure-fs test fixture");
            Self { path }
        }
    }

    impl Drop for Fixture {
        fn drop(&mut self) {
            fs::remove_dir_all(&self.path).expect("remove secure-fs test fixture");
        }
    }

    fn forced_enosys_open(parent: RawFd, name: &str, flags: i32, mode: u32) -> io::Result<File> {
        secure_openat_with(parent, name, flags, mode, |_, _, _, _| {
            Err(io::Error::from_raw_os_error(libc::ENOSYS))
        })
    }

    #[test]
    fn enosys_fallback_is_descriptor_anchored() {
        let fixture = Fixture::new();
        let original = fixture.path.join("parent");
        fs::create_dir(&original).unwrap();
        fs::write(original.join("value"), b"retained").unwrap();
        let parent = File::open(&original).unwrap();

        let moved = fixture.path.join("parent-retained");
        fs::rename(&original, &moved).unwrap();
        fs::create_dir(&original).unwrap();
        fs::write(original.join("value"), b"replacement").unwrap();

        let mut opened =
            forced_enosys_open(parent.as_raw_fd(), "value", libc::O_RDONLY, 0).unwrap();
        let mut bytes = Vec::new();
        opened.read_to_end(&mut bytes).unwrap();
        assert_eq!(bytes, b"retained");
    }

    #[test]
    fn enosys_fallback_rejects_symlinks_and_non_components() {
        let fixture = Fixture::new();
        fs::write(fixture.path.join("target"), b"target").unwrap();
        symlink("target", fixture.path.join("link")).unwrap();
        let parent = File::open(&fixture.path).unwrap();

        let symlink_error =
            forced_enosys_open(parent.as_raw_fd(), "link", libc::O_RDONLY, 0).unwrap_err();
        assert_eq!(symlink_error.raw_os_error(), Some(libc::ELOOP));

        for invalid in ["", ".", "..", "../target", "subdir/target"] {
            let error =
                forced_enosys_open(parent.as_raw_fd(), invalid, libc::O_RDONLY, 0).unwrap_err();
            assert_eq!(error.kind(), io::ErrorKind::InvalidInput);
        }
    }

    #[test]
    fn enosys_fallback_supports_directory_and_exclusive_create_flags() {
        let fixture = Fixture::new();
        fs::create_dir(fixture.path.join("directory")).unwrap();
        let parent = File::open(&fixture.path).unwrap();

        let directory = forced_enosys_open(
            parent.as_raw_fd(),
            "directory",
            libc::O_RDONLY | libc::O_DIRECTORY,
            0,
        )
        .unwrap();
        assert_eq!(
            fstat(&directory).unwrap().st_mode & libc::S_IFMT,
            libc::S_IFDIR
        );

        let created = forced_enosys_open(
            parent.as_raw_fd(),
            "created",
            libc::O_WRONLY | libc::O_CREAT | libc::O_EXCL,
            0o600,
        )
        .unwrap();
        assert_eq!(fstat(&created).unwrap().st_mode & 0o777, 0o600);
        drop(created);

        let duplicate_error = forced_enosys_open(
            parent.as_raw_fd(),
            "created",
            libc::O_WRONLY | libc::O_CREAT | libc::O_EXCL,
            0o600,
        )
        .unwrap_err();
        assert_eq!(duplicate_error.raw_os_error(), Some(libc::EEXIST));
    }

    #[test]
    fn secure_openat_falls_back_only_for_enosys() {
        let fixture = Fixture::new();
        fs::write(fixture.path.join("value"), b"value").unwrap();
        let parent = File::open(&fixture.path).unwrap();

        let error = secure_openat_with(
            parent.as_raw_fd(),
            "value",
            libc::O_RDONLY,
            0,
            |_, _, _, _| Err(io::Error::from_raw_os_error(libc::EPERM)),
        )
        .unwrap_err();
        assert_eq!(error.raw_os_error(), Some(libc::EPERM));
    }
}

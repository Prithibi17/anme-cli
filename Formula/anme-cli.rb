class AnmeCli < Formula
  desc "Terminal anime browser and MPV controller"
  homepage "https://github.com/Prithibi17/anme-cli"
  license "GPL-3.0"
  head "https://github.com/Prithibi17/anme-cli.git", branch: "main"

  depends_on "ffmpeg"
  depends_on "fzf"
  depends_on "grep"
  depends_on "yt-dlp"
  depends_on "mpv" => :recommended

  def install
    bin.install "anme-cli"
    man1.install "anme-cli.1"
  end

  def caveats
    <<~EOS
      On macOS you can install IINA player instead of mpv for better experience:
        brew install --cask iina
    EOS
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/anme-cli --version")
    assert_match "No results found!", shell_output("#{bin}/anme-cli this-title-does-not-exist-for-sure 2>&1", 1)
  end
end

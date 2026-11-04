# `timed <seconds> <label> <command…>` runs a step in its own process group, without stdin, and reports its time.
# Past the limit or on a signal it sends the group SIGINT (Playwright and Firebase then stop what they started),
# then TERM, then KILL; it returns 142 past the limit, 130 when stopped, else the step's own status.
timed() {
  local limit="$1" label="$2" start=$SECONDS status=0
  shift 2
  echo "=== $label ===" >&2
  perl -MPOSIX=:sys_wait_h -e '
    my $limit = shift;
    my $grace = $ENV{TIMED_NESTED} ? 15 : 30;
    my $pid = fork() // die "cannot fork: $!\n";
    if (!$pid) {
      setpgrp(0, 0);
      open STDIN, "<", "/dev/null";
      $ENV{TIMED_NESTED} = 1;
      exec @ARGV or die "cannot run $ARGV[0]: $!\n";
    }
    setpgrp($pid, 0);
    my $status;
    my $empty = sub {
      $status = $? if !defined $status && waitpid($pid, WNOHANG) == $pid;
      return !kill(0, -$pid);
    };
    # Each signal gets its time, but once the step itself has gone, what it left behind gets 3 s before the next one.
    my $stop = sub {
      my $code = shift;
      for my $signal (["INT", $grace], ["TERM", 5], ["KILL", 1]) {
        kill $signal->[0], -$pid;
        for my $second (1 .. $signal->[1]) {
          last if $empty->() || (defined $status && $second > 3);
          sleep 1;
        }
        last if $empty->();
      }
      exit $code;
    };
    $SIG{ALRM} = sub { $stop->(142) };
    $SIG{$_} = sub { $stop->(130) } for qw(INT TERM HUP QUIT);
    alarm $limit;
    waitpid $pid, 0;
    $status = $?;
    kill "TERM", -$pid;
    exit($status & 127 ? 128 + ($status & 127) : $status >> 8);
  ' "$limit" "$@" || status=$?
  echo "--- $label: $((SECONDS - start)) s of $limit s" >&2
  if [[ $status -eq 142 ]]; then echo "TIMEOUT: $label ran past $limit s; it and what it started are stopped" >&2; fi
  return "$status"
}

# `step <seconds> <label> <command…>`: `timed`, its output kept in a log under $GATE_LOGS. A pass prints one line; a
# failure prints the step's last 40 lines, or the block of the nested step that failed first, and the log's path.
step() {
  local limit="$1" label="$2" start=$SECONDS status=0 log
  log="${GATE_LOGS:?}/$(printf '%s' "$label" | tr -cs 'A-Za-z0-9' '-' | cut -c1-60).log"
  timed "$@" > "$log" 2>&1 || status=$?
  if [[ $status -eq 0 ]]; then
    echo "PASS $label: $((SECONDS - start)) s of $limit s" >&2
    return 0
  fi
  echo "FAIL $label: $((SECONDS - start)) s of $limit s" >&2
  if grep -q '^FAIL ' "$log"; then sed -n '/^FAIL /,$p' "$log" | head -n 60 >&2; else tail -n 40 "$log" >&2; fi
  echo "  log: $log" >&2
  return "$status"
}

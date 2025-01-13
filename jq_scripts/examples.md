### 모든 twins의 info 출력
```list_twins```

### 'test'에 해당하는 twin의 info 출력
```list_twins id=test```

### 모든 twins의 id 출력
```list_twins | to_id```

### RUNNING 상태의 twin들의 id 출력
```list_twins | filter status=RUNNING | to_id```

### RUNNING 상태가 아닌 twins 중에서 하나를 선택해서 시작 시킨
```list_twins | filter_not status=RUNNING | fzf | xargs -I {} mdt start {}```

### RUNNING 상태의 twin들의 요약 정보 출력
```list_twins | filter status=RUNNING | summarize```